"""Grava no banco o que os adaptadores encontraram. Igual para todas as fontes.

Regras:
- Concurso é identificado por chave_externa: rodar a coleta duas vezes não duplica.
- Concurso marcado como "revisado" só tem a situação e as inscrições atualizadas;
  o resto foi conferido por você e não é sobrescrito.
- Documento novo é baixado, guardado bruto (imutável) e tem o texto extraído.
- Tudo que é novo vira EventoDominio, que alimenta avisos e futuras features.
"""
import logging
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction

from catalogo.classificacao import classificar_concurso
from catalogo.models import Banca, Cargo, Concurso, Modalidade, Vaga

from .adaptadores.base import Adaptador, ConcursoExtraido, DocumentoExtraido, ResultadoColeta
from .armazenamento import salvar_bruto
from .classificador import classificar_tipo
from .models import Documento, EventoDominio, Fonte, TipoDocumento
from .pdf import extrair_texto_pdf

log = logging.getLogger(__name__)


@dataclass
class Contagem:
    concursos_vistos: int = 0
    concursos_novos: int = 0
    documentos_novos: int = 0

    def somar(self, outra: "Contagem"):
        self.concursos_vistos += outra.concursos_vistos
        self.concursos_novos += outra.concursos_novos
        self.documentos_novos += outra.documentos_novos


def emitir(tipo, concurso=None, documento=None, **payload):
    return EventoDominio.objects.create(tipo=tipo, concurso=concurso, documento=documento, payload=payload)


def persistir(
    fonte: Fonte,
    adaptador: Adaptador,
    resultado: ResultadoColeta,
    baixar_arquivos: bool | None = None,
) -> Contagem:
    baixar = settings.COLETA_BAIXAR_ARQUIVOS if baixar_arquivos is None else baixar_arquivos
    contagem = Contagem()
    for extraido in resultado.concursos:
        contagem.somar(_persistir_concurso(fonte, adaptador, extraido, baixar))
    for doc in resultado.documentos_soltos:
        if _persistir_documento(fonte, adaptador, doc, None, baixar):
            contagem.documentos_novos += 1
    return contagem


@transaction.atomic
def _persistir_concurso(fonte, adaptador, extraido: ConcursoExtraido, baixar: bool) -> Contagem:
    contagem = Contagem(concursos_vistos=1)
    banca = Banca.objects.filter(slug=extraido.banca_slug).first() if extraido.banca_slug else None

    concurso = Concurso.objects.filter(chave_externa=extraido.chave_externa).first()
    novo = concurso is None
    if novo:
        concurso = Concurso(chave_externa=extraido.chave_externa)
    situacao_anterior = None if novo else concurso.situacao

    if novo or not concurso.revisado:
        concurso.titulo = extraido.titulo[:400]
        concurso.banca = banca or concurso.banca
        concurso.ano = extraido.ano or concurso.ano
        concurso.url_oficial = extraido.url_oficial or concurso.url_oficial
        concurso.maturidade = max(concurso.maturidade or "", extraido.maturidade)
        concurso.vagas_total = extraido.vagas_total or concurso.vagas_total
        concurso.remuneracao_maxima = extraido.remuneracao_maxima or concurso.remuneracao_maxima
        concurso.atributos = {**(concurso.atributos or {}), **extraido.atributos}
    concurso.situacao = extraido.situacao or concurso.situacao
    concurso.inscricoes_inicio = extraido.inscricoes_inicio or concurso.inscricoes_inicio
    concurso.inscricoes_fim = extraido.inscricoes_fim or concurso.inscricoes_fim

    if extraido.bruto:
        caminho, _ = salvar_bruto(fonte.slug, extraido.bruto, extraido.bruto_extensao)
        concurso.atributos = {**concurso.atributos, "_bruto_fonte": caminho}
    concurso.save()

    if novo:
        contagem.concursos_novos = 1
        emitir(
            EventoDominio.Tipo.CONCURSO_DESCOBERTO,
            concurso=concurso,
            titulo=concurso.titulo,
            fonte=fonte.slug,
            situacao=concurso.situacao,
        )
    elif situacao_anterior != concurso.situacao:
        emitir(
            EventoDominio.Tipo.CONCURSO_MUDOU_SITUACAO,
            concurso=concurso,
            titulo=concurso.titulo,
            de=situacao_anterior,
            para=concurso.situacao,
        )

    if not concurso.revisado:
        for cargo_ext in extraido.cargos:
            cargo, _ = Cargo.objects.get_or_create(
                concurso=concurso,
                nome=cargo_ext.nome[:400],
                defaults={"codigo_externo": cargo_ext.codigo_externo, "remuneracao": cargo_ext.remuneracao},
            )
            if cargo_ext.vagas is not None:
                Vaga.objects.update_or_create(
                    cargo=cargo,
                    localidade="",
                    modalidade=Modalidade.TOTAL,
                    defaults={"quantidade": cargo_ext.vagas},
                )
    classificar_concurso(concurso)

    for doc in extraido.documentos:
        if _persistir_documento(fonte, adaptador, doc, concurso, baixar):
            contagem.documentos_novos += 1
    return contagem


def _persistir_documento(fonte, adaptador, doc: DocumentoExtraido, concurso, baixar: bool) -> Documento | None:
    if Documento.objects.filter(fonte=fonte, chave_externa=doc.chave_externa).exists():
        return None

    documento = Documento(
        fonte=fonte,
        concurso=concurso,
        chave_externa=doc.chave_externa[:300],
        titulo=doc.titulo[:600],
        url=doc.url,
        publicado_em=doc.publicado_em,
        texto=doc.texto,
        metadados=dict(doc.metadados),
    )

    conteudo = doc.conteudo
    if conteudo is None and baixar and doc.url:
        try:
            conteudo = adaptador.baixar_arquivo(doc)
        except Exception as erro:  # um arquivo fora do ar não derruba a coleta
            log.warning("Não foi possível baixar %s: %s", doc.url, erro)
            documento.metadados["erro_download"] = str(erro)[:300]
    if conteudo:
        documento.arquivo, documento.sha256 = salvar_bruto(fonte.slug, conteudo, doc.extensao)
        if doc.extensao == "pdf" and not documento.texto:
            documento.texto = extrair_texto_pdf(conteudo)
            # PDF sem texto = provavelmente imagem escaneada → precisa de OCR/revisão.
            documento.precisa_revisao = not documento.texto

    documento.tipo = (
        doc.tipo if doc.tipo and doc.tipo != TipoDocumento.OUTRO else classificar_tipo(doc.titulo, documento.texto)
    )
    if documento.tipo == TipoDocumento.OUTRO and concurso is None:
        documento.precisa_revisao = True
    documento.save()

    emitir(
        EventoDominio.Tipo.DOCUMENTO_PUBLICADO,
        concurso=concurso,
        documento=documento,
        titulo=documento.titulo,
        tipo_documento=documento.tipo,
        fonte=fonte.slug,
    )
    return documento
