"""Transforma eventos de domínio num resumo diário por e-mail.

Um evento entra no resumo quando casa com pelo menos um FiltroAlerta ativo.
Falhas de coleta sempre entram. Sem filtros cadastrados, só as falhas.

Proteções contra a enxurrada de avisos:
- documento publicado há mais de `dias_documento` dias não entra;
- concurso descoberto já encerrado ou homologado não entra (coleta de histórico);
- a primeira coleta de cada fonte não gera aviso (ver coleta.py);
- sai no máximo um resumo por dia, com até AVISOS_MAX_CONCURSOS concursos.

Os eventos só são marcados como processados depois que o e-mail sai. Se o envio
falhar, eles ficam para a próxima rotina.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from catalogo.models import Concurso, FiltroAlerta, Situacao

from .models import Documento, EventoDominio, ResumoAviso
from .texto import normalizar

log = logging.getLogger(__name__)

SITUACOES = dict(Situacao.choices)
# Concurso que já chega encerrado veio de coleta de histórico, não é novidade.
JA_ENCERRADO = {Situacao.ENCERRADO, Situacao.HOMOLOGADO}
MAX_DOCUMENTOS_POR_CONCURSO = 10
MAX_DOCUMENTOS_SOLTOS = 30


def casa(filtro: FiltroAlerta, concurso: Concurso | None, documento: Documento | None = None, tipo_evento: str = "") -> bool:
    if filtro.tipos_documento and tipo_evento == EventoDominio.Tipo.DOCUMENTO_PUBLICADO:
        if not documento or documento.tipo not in filtro.tipos_documento:
            return False

    # .all() aproveita o prefetch_related; values_list faria uma consulta por evento.
    bancas = {b.id for b in filtro.bancas.all()}
    if bancas and (not concurso or concurso.banca_id not in bancas):
        return False

    if filtro.esferas and (not concurso or concurso.esfera not in filtro.esferas):
        return False

    areas = {a.id for a in filtro.areas.all()}
    if areas:
        if not concurso:
            return False
        if not areas & {a.id for a in concurso.areas.all()}:
            return False

    if filtro.palavras_chave:
        alvo = normalizar(" ".join(filter(None, [concurso.titulo if concurso else "", documento.titulo if documento else ""])))
        if not any(normalizar(p) in alvo for p in filtro.palavras_chave):
            return False
    return True


def relevante(evento: EventoDominio, filtros: list[FiltroAlerta], limite_documento: datetime) -> bool:
    if evento.tipo == EventoDominio.Tipo.COLETA_FALHOU:
        return True
    documento = evento.documento
    if evento.tipo == EventoDominio.Tipo.DOCUMENTO_PUBLICADO and documento and documento.publicado_em:
        if documento.publicado_em < limite_documento:
            return False
    if evento.tipo == EventoDominio.Tipo.CONCURSO_DESCOBERTO and evento.concurso:
        if evento.concurso.situacao in JA_ENCERRADO:
            return False
    return any(casa(f, evento.concurso, documento, evento.tipo) for f in filtros)


def link_painel(concurso: Concurso) -> str:
    return f"{settings.SITE_URL}/admin/catalogo/concurso/{concurso.pk}/change/"


@dataclass
class Prazo:
    concurso: Concurso
    fim: datetime
    dias: int

    @property
    def quando(self) -> str:
        if self.dias == 0:
            return "hoje"
        return "amanhã" if self.dias == 1 else f"em {self.dias} dias"


@dataclass
class Novidade:
    """O que aconteceu com um concurso desde o último resumo."""

    concurso: Concurso
    novo: bool = False
    situacao: tuple[str, str] | None = None
    documentos: list[Documento] = field(default_factory=list)

    @property
    def link(self) -> str:
        return link_painel(self.concurso)

    @property
    def mudanca(self) -> str:
        if not self.situacao:
            return ""
        de, para = self.situacao
        return f"{SITUACOES.get(de, de)} → {SITUACOES.get(para, para)}"

    @property
    def documentos_visiveis(self) -> list[Documento]:
        return self.documentos[:MAX_DOCUMENTOS_POR_CONCURSO]

    @property
    def documentos_omitidos(self) -> int:
        return max(0, len(self.documentos) - MAX_DOCUMENTOS_POR_CONCURSO)


def plural(n: int, singular: str, plural_: str) -> str:
    return f"{n} {singular if n == 1 else plural_}"


@dataclass
class Resumo:
    data: datetime
    falhas: list[dict] = field(default_factory=list)
    prazos: list[Prazo] = field(default_factory=list)
    novidades: list[Novidade] = field(default_factory=list)
    concursos_omitidos: int = 0
    soltos: list[Documento] = field(default_factory=list)
    soltos_omitidos: int = 0

    @property
    def vazio(self) -> bool:
        return not (self.falhas or self.prazos or self.novidades or self.soltos)

    @property
    def link_concursos(self) -> str:
        return f"{settings.SITE_URL}/admin/catalogo/concurso/"

    @property
    def link_soltos(self) -> str:
        return f"{settings.SITE_URL}/admin/ingestao/documento/?vinculado=nao"

    def assunto(self) -> str:
        partes = []
        total = len(self.novidades) + self.concursos_omitidos
        if total:
            partes.append(plural(total, "concurso com novidades", "concursos com novidades"))
        if self.prazos:
            partes.append(plural(len(self.prazos), "prazo de inscrição", "prazos de inscrição"))
        soltos = len(self.soltos) + self.soltos_omitidos
        if soltos:
            partes.append(plural(soltos, "ato sem concurso", "atos sem concurso"))
        if self.falhas:
            partes.append(plural(len(self.falhas), "falha de coleta", "falhas de coleta"))
        return "ConcursoHub: " + ", ".join(partes)

    def texto(self) -> str:
        linhas = [f"Resumo do ConcursoHub — {timezone.localtime(self.data):%d/%m/%Y}", ""]
        if self.falhas:
            linhas.append("FALHAS DE COLETA")
            linhas += [f"- {f.get('fonte')}: {f.get('erro', '')}" for f in self.falhas]
            linhas.append("")
        if self.prazos:
            linhas.append("INSCRIÇÕES TERMINANDO")
            for p in self.prazos:
                linhas.append(f"- {timezone.localtime(p.fim):%d/%m} ({p.quando}): {p.concurso.titulo}")
                if p.concurso.url_oficial:
                    linhas.append(f"  {p.concurso.url_oficial}")
            linhas.append("")
        if self.novidades:
            linhas.append("NOVIDADES")
            for n in self.novidades:
                marcas = (["novo"] if n.novo else []) + ([f"situação: {n.mudanca}"] if n.situacao else [])
                linhas.append(n.concurso.titulo + (f" [{'; '.join(marcas)}]" if marcas else ""))
                for d in n.documentos_visiveis:
                    linhas.append(f"  - {d.get_tipo_display()}: {d.titulo}")
                    if d.url:
                        linhas.append(f"    {d.url}")
                if n.documentos_omitidos:
                    linhas.append(f"  - e mais {plural(n.documentos_omitidos, 'documento', 'documentos')}")
                linhas.append(f"  Painel: {n.link}")
                linhas.append("")
            if self.concursos_omitidos:
                linhas.append(
                    f"E mais {plural(self.concursos_omitidos, 'concurso', 'concursos')} com novidades: {self.link_concursos}"
                )
                linhas.append("")
        if self.soltos:
            linhas.append("ATOS SEM CONCURSO VINCULADO")
            for d in self.soltos:
                linhas.append(f"- {d.get_tipo_display()}: {d.titulo}")
                if d.url:
                    linhas.append(f"  {d.url}")
            if self.soltos_omitidos:
                linhas.append(f"- e mais {self.soltos_omitidos}: {self.link_soltos}")
            linhas.append("")
        return "\n".join(linhas).strip() + "\n"

    def html(self) -> str:
        return render_to_string("ingestao/resumo_email.html", {"resumo": self})


def prazos_proximos(filtros: list[FiltroAlerta], agora: datetime, dias: int) -> list[Prazo]:
    if not filtros:
        return []
    candidatos = (
        Concurso.objects.filter(inscricoes_fim__gte=agora, inscricoes_fim__lte=agora + timedelta(days=dias))
        .prefetch_related("areas")
        .order_by("inscricoes_fim")
    )
    hoje = timezone.localtime(agora).date()
    return [
        Prazo(c, c.inscricoes_fim, (timezone.localtime(c.inscricoes_fim).date() - hoje).days)
        for c in candidatos
        if any(casa(f, c) for f in filtros)
    ]


def montar(eventos: list[EventoDominio], prazos: list[Prazo], agora: datetime) -> Resumo:
    resumo = Resumo(data=agora, prazos=prazos)
    por_concurso: dict[int, Novidade] = {}
    soltos = []
    for evento in eventos:
        if evento.tipo == EventoDominio.Tipo.COLETA_FALHOU:
            resumo.falhas.append(evento.payload or {})
            continue
        if not evento.concurso:
            if evento.documento:
                soltos.append(evento.documento)
            continue
        novidade = por_concurso.setdefault(evento.concurso_id, Novidade(evento.concurso))
        if evento.tipo == EventoDominio.Tipo.CONCURSO_DESCOBERTO:
            novidade.novo = True
        elif evento.tipo == EventoDominio.Tipo.CONCURSO_MUDOU_SITUACAO:
            p = evento.payload or {}
            # Várias mudanças no mesmo dia: vale a primeira origem e o último destino.
            de = novidade.situacao[0] if novidade.situacao else p.get("de", "")
            novidade.situacao = (de, p.get("para", ""))
        elif evento.documento:
            novidade.documentos.append(evento.documento)

    # Concursos novos e mudanças de situação primeiro; depois os com mais documentos.
    novidades = sorted(por_concurso.values(), key=lambda n: (not n.novo, n.situacao is None, -len(n.documentos)))
    limite = settings.AVISOS_MAX_CONCURSOS
    resumo.novidades, resumo.concursos_omitidos = novidades[:limite], max(0, len(novidades) - limite)
    resumo.soltos, resumo.soltos_omitidos = soltos[:MAX_DOCUMENTOS_SOLTOS], max(0, len(soltos) - MAX_DOCUMENTOS_SOLTOS)
    return resumo


def enviar(resumo: Resumo) -> ResumoAviso:
    """Envia o resumo e registra a tentativa. Sem AVISOS_EMAIL_PARA, só registra no log."""
    registro = ResumoAviso(
        enviado_em=resumo.data,
        destinatario=settings.AVISOS_EMAIL_PARA,
        assunto=resumo.assunto()[:200],
        texto=resumo.texto(),
    )
    if not settings.AVISOS_EMAIL_PARA:
        log.info("RESUMO (sem AVISOS_EMAIL_PARA no .env; só no log)\n%s", registro.texto)
    else:
        mensagem = EmailMultiAlternatives(
            registro.assunto, registro.texto, settings.DEFAULT_FROM_EMAIL, [settings.AVISOS_EMAIL_PARA]
        )
        mensagem.attach_alternative(resumo.html(), "text/html")
        try:
            mensagem.send()
        except Exception as erro:  # SMTP fora do ar, senha errada, sem internet
            log.warning("Não foi possível enviar o resumo: %s", erro)
            registro.ok = False
            registro.erro = str(erro)[:2000]
    registro.save()
    return registro


@dataclass
class Resultado:
    processados: int = 0
    resumo: ResumoAviso | None = None
    motivo: str = ""


def processar(
    dias_documento: int = 15,
    agora: datetime | None = None,
    forcar: bool = False,
    previa: bool = False,
) -> Resultado:
    """Monta e envia o resumo do dia com os eventos pendentes.

    Antes de AVISOS_HORA, ou se o resumo de hoje já saiu, não faz nada (a menos
    que `forcar`). Com `previa`, devolve o texto em `motivo` sem enviar nem marcar."""
    agora = agora or timezone.now()
    local = timezone.localtime(agora)
    if not (forcar or previa):
        if local.hour < settings.AVISOS_HORA:
            return Resultado(motivo=f"o resumo do dia sai a partir das {settings.AVISOS_HORA}h")
        if ResumoAviso.objects.filter(ok=True, enviado_em__date=local.date()).exists():
            return Resultado(motivo="o resumo de hoje já foi enviado")

    filtros = list(FiltroAlerta.objects.filter(ativo=True).prefetch_related("bancas", "areas"))
    pendentes = list(
        EventoDominio.objects.filter(processado_em__isnull=True)
        .select_related("concurso", "documento")
        .prefetch_related("concurso__areas")
    )
    limite = agora - timedelta(days=dias_documento)
    avisados = [e for e in pendentes if relevante(e, filtros, limite)]
    resumo = montar(avisados, prazos_proximos(filtros, agora, settings.AVISOS_DIAS_PRAZO), agora)

    if previa:
        return Resultado(motivo="nada a avisar" if resumo.vazio else f"{resumo.assunto()}\n\n{resumo.texto()}")
    if resumo.vazio:
        _marcar(pendentes, agora)
        return Resultado(processados=len(pendentes), motivo="nada novo nos seus filtros")

    registro = enviar(resumo)
    if not registro.ok:
        return Resultado(resumo=registro, motivo=f"falha no envio, os eventos ficam para a próxima: {registro.erro}")
    avisados_ids = {e.id for e in avisados}
    _marcar([e for e in pendentes if e.id not in avisados_ids], agora)
    _marcar(avisados, agora, registro)
    return Resultado(processados=len(pendentes), resumo=registro, motivo=registro.assunto)


def _marcar(eventos: list[EventoDominio], agora: datetime, resumo: ResumoAviso | None = None) -> None:
    ids = [e.id for e in eventos]
    # Em lotes: o SQLite limita o número de parâmetros por consulta.
    for inicio in range(0, len(ids), 500):
        EventoDominio.objects.filter(id__in=ids[inicio : inicio + 500]).update(processado_em=agora, resumo=resumo)
