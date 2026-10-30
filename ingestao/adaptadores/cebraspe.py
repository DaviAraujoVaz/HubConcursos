"""Cebraspe — usa a API JSON que o próprio site consome.

Endpoints (encontrados inspecionando www.cebraspe.org.br/concursos em 29/10/2026):
  lista:    https://apis.cebraspe.org.br/cebraspe/eventos/tipo/concursos/
            → [{faseEvento, ordem, eventos: [{eventoURL, eventoNomeAbreviado, eventoStatus, …}]}]
  detalhe:  https://apis.cebraspe.org.br/cebraspe/eventos/<eventoURL>
            → {eventoCargos, arquivosEdital, arquivosGabarito, periodoInscricao, …}
  arquivo:  https://cdn.cebraspe.org.br/concursos/<eventoURL>/arquivos/<nomeArquivo>

Se o site mudar, é aqui (e só aqui) que se mexe.
"""
import json
import logging
import re

from catalogo.models import Situacao

from ..texto import limpar_espacos, parse_decimal, parse_inteiro, parse_iso, parse_periodo_br
from .base import Adaptador, CargoExtraido, ConcursoExtraido, DocumentoExtraido, ResultadoColeta, registrar

log = logging.getLogger(__name__)

URL_LISTA = "https://apis.cebraspe.org.br/cebraspe/eventos/tipo/concursos/"
URL_DETALHE = "https://apis.cebraspe.org.br/cebraspe/eventos/{slug}"
URL_ARQUIVO = "https://cdn.cebraspe.org.br/concursos/{slug}/arquivos/{arquivo}"
URL_PAGINA = "https://www.cebraspe.org.br/concursos/{slug}"

SITUACAO_POR_STATUS = {
    "novos": Situacao.PREVISTO,
    "inscricoes-abertas": Situacao.ABERTO,
    "em-andamento": Situacao.ANDAMENTO,
    "encerrado": Situacao.ENCERRADO,
}
STATUS_ATIVOS = ("novos", "inscricoes-abertas", "em-andamento")

_PREFIXO_CARGO = re.compile(r"^\s*cargo\s*\d+\s*[:\-–]\s*", re.IGNORECASE)


@registrar
class CebraspeAdaptador(Adaptador):
    slug = "cebraspe"
    nome = "Cebraspe"

    def listar(self) -> list[dict]:
        """Eventos da lista, já achatados, cada um com o status da fase."""
        fases = self.cliente.get(URL_LISTA).json()
        eventos = []
        for fase in fases:
            for evento in fase.get("eventos") or []:
                eventos.append(evento)
        return eventos

    def coletar(self, incluir_encerrados: bool = False, apenas: list[str] | None = None, **_):
        eventos = self.listar()
        for evento in eventos:
            slug = evento.get("eventoURL")
            status = (evento.get("eventoStatus") or "").lower()
            if not slug:
                continue
            if apenas and slug not in apenas:
                continue
            if not incluir_encerrados and status not in STATUS_ATIVOS:
                continue
            resposta = self.cliente.get(URL_DETALHE.format(slug=slug))
            detalhe = resposta.json()
            yield ResultadoColeta(concursos=[converter(evento, detalhe, resposta.content)])


def converter(evento: dict, detalhe: dict, bruto: bytes | None = None) -> ConcursoExtraido:
    """Transforma o par (item da lista, detalhe) num ConcursoExtraido. Função pura, testável."""
    slug = evento["eventoURL"]
    status = (evento.get("eventoStatus") or "").lower()
    inicio, fim = parse_periodo_br(detalhe.get("periodoInscricao") or "")

    cargos = []
    for item in detalhe.get("eventoCargos") or []:
        nome = _PREFIXO_CARGO.sub("", limpar_espacos(item.get("area") or ""))
        if nome:
            cargos.append(CargoExtraido(nome=nome, codigo_externo=item.get("idArea") or ""))

    documentos = []
    for grupo in ("arquivosEdital", "arquivosGabarito"):
        for arquivo in detalhe.get(grupo) or []:
            nome_arquivo = arquivo.get("nomeArquivo") or ""
            extensao = nome_arquivo.rsplit(".", 1)[-1].lower() if "." in nome_arquivo else ""
            # Cada documento vem em PDF e numa versão HTML (VLibras); fica só o PDF.
            if extensao != "pdf":
                continue
            descricao = limpar_espacos(arquivo.get("descricaoArquivo") or nome_arquivo)
            documentos.append(
                DocumentoExtraido(
                    chave_externa=f"{slug}/{nome_arquivo}",
                    titulo=descricao,
                    url=URL_ARQUIVO.format(slug=slug, arquivo=nome_arquivo),
                    tipo="gabarito" if grupo == "arquivosGabarito" else "outro",
                    publicado_em=parse_iso(arquivo.get("dataArquivoObj") or ""),
                    extensao="pdf",
                    metadados={"grupo": grupo},
                )
            )

    # Às vezes eventoNomeCompleto é só a URL ("ADEAL_26"); aí a abreviação é melhor.
    nomes = (
        detalhe.get("eventoNomeCompleto"),
        evento.get("eventoNomeCompleto"),
        detalhe.get("eventoNomeAbreviado"),
        evento.get("eventoNomeAbreviado"),
    )
    titulo = next((limpar_espacos(n) for n in nomes if n and n != slug), slug.replace("_", " "))
    return ConcursoExtraido(
        chave_externa=f"cebraspe:{slug}",
        titulo=titulo,
        banca_slug="cebraspe",
        url_oficial=URL_PAGINA.format(slug=slug),
        ano=evento.get("eventoAno") or detalhe.get("eventoAno"),
        situacao=SITUACAO_POR_STATUS.get(status, Situacao.ANDAMENTO),
        inscricoes_inicio=inicio,
        inscricoes_fim=fim,
        vagas_total=parse_inteiro(detalhe.get("eventoTotalVagas") or evento.get("eventoTotalVagas")),
        remuneracao_maxima=parse_decimal(detalhe.get("eventoSalarioMaximo") or evento.get("eventoSalarioMaximo")),
        cargos=cargos,
        documentos=documentos,
        atributos={"cebraspe_id": evento.get("idEvento"), "cebraspe_status": status},
        bruto=bruto if bruto is not None else json.dumps(detalhe, ensure_ascii=False).encode(),
        bruto_extensao="json",
    )
