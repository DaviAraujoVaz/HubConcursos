"""FGV Conhecimento — HTML servido direto (Drupal).

Estrutura (inspecionada em conhecimento.fgv.br/concursos em 29/10/2026):
  lista:   /concursos?page=N com duas listas na mesma página:
           .view-id-concursos_em_andamento e .view-id-concursos_realizados,
           cada item em `.views-field-title a`. O mesmo ?page=N pagina as duas.
  detalhe: título em <h1>, situação em `.field--name-field-concurso-status`,
           arquivos em blocos `.paragraph--type--texto-data`, cada um com
           <time datetime=…> e um link para /sites/default/files/concursos/….pdf
"""
import logging
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from catalogo.models import Situacao

from ..texto import limpar_espacos, normalizar, parse_iso
from .base import Adaptador, ConcursoExtraido, DocumentoExtraido, ResultadoColeta, registrar

log = logging.getLogger(__name__)

BASE = "https://conhecimento.fgv.br"
URL_LISTA = BASE + "/concursos?page={pagina}"
SELETOR_ANDAMENTO = ".view-id-concursos_em_andamento .views-field-title a[href]"
SELETOR_REALIZADOS = ".view-id-concursos_realizados .views-field-title a[href]"
MAX_PAGINAS = 40


@registrar
class FgvAdaptador(Adaptador):
    slug = "fgv"
    nome = "FGV Conhecimento"

    def listar(self, incluir_realizados: bool = False) -> list[tuple[str, str, bool]]:
        """[(url, título, em_andamento)] percorrendo as páginas até não haver itens novos."""
        vistos: dict[str, tuple[str, str, bool]] = {}
        for pagina in range(MAX_PAGINAS):
            html = self.cliente.get(URL_LISTA.format(pagina=pagina)).text
            itens = parse_lista(html, incluir_realizados)
            novos = [item for item in itens if item[0] not in vistos]
            if not novos:
                break
            for item in novos:
                vistos[item[0]] = item
        return list(vistos.values())

    def coletar(self, incluir_encerrados: bool = False, apenas: list[str] | None = None, **_):
        for url, titulo_lista, em_andamento in self.listar(incluir_realizados=incluir_encerrados):
            caminho = urlparse(url).path.strip("/")
            if apenas and caminho not in apenas:
                continue
            resposta = self.cliente.get(url)
            yield ResultadoColeta(
                concursos=[converter_detalhe(url, resposta.text, titulo_lista, em_andamento, resposta.content)]
            )


def parse_lista(html: str, incluir_realizados: bool = False) -> list[tuple[str, str, bool]]:
    sopa = BeautifulSoup(html, "lxml")
    itens = [(urljoin(BASE, a["href"]), limpar_espacos(a.get_text()), True) for a in sopa.select(SELETOR_ANDAMENTO)]
    if incluir_realizados:
        itens += [(urljoin(BASE, a["href"]), limpar_espacos(a.get_text()), False) for a in sopa.select(SELETOR_REALIZADOS)]
    return itens


def _situacao(texto_status: str, em_andamento: bool) -> str:
    status = normalizar(texto_status)
    if "inscri" in status and "abert" in status:
        return Situacao.ABERTO
    if "encerr" in status or "realizad" in status or "conclu" in status:
        return Situacao.ENCERRADO
    if "andamento" in status:
        return Situacao.ANDAMENTO
    return Situacao.ANDAMENTO if em_andamento else Situacao.ENCERRADO


def converter_detalhe(url: str, html: str, titulo_lista: str = "", em_andamento: bool = True, bruto: bytes | None = None):
    sopa = BeautifulSoup(html, "lxml")
    h1 = sopa.find("h1")
    titulo = limpar_espacos(h1.get_text()) if h1 else ""
    if not titulo or titulo == "ㅤ":
        titulo = titulo_lista
    status_el = sopa.select_one(".field--name-field-concurso-status")
    situacao = _situacao(status_el.get_text() if status_el else "", em_andamento)

    documentos = []
    for bloco in sopa.select(".paragraph--type--texto-data"):
        tempo = bloco.find("time")
        publicado_em = parse_iso(tempo.get("datetime", "")) if tempo else None
        for link in bloco.select("a[href]"):
            href = urljoin(BASE, link["href"])
            if not href.lower().endswith(".pdf"):
                continue  # links de inscrição, certificado etc.
            documentos.append(
                DocumentoExtraido(
                    chave_externa=urlparse(href).path,
                    titulo=limpar_espacos(link.get_text()) or href.rsplit("/", 1)[-1],
                    url=href,
                    publicado_em=publicado_em,
                    extensao="pdf",
                )
            )

    anos = [d.publicado_em.year for d in documentos if d.publicado_em]
    caminho = urlparse(url).path.strip("/")
    return ConcursoExtraido(
        chave_externa=f"fgv:{caminho}",
        titulo=titulo or caminho,
        banca_slug="fgv",
        url_oficial=url,
        ano=min(anos) if anos else None,
        situacao=situacao,
        documentos=documentos,
        bruto=bruto if bruto is not None else html.encode(),
        bruto_extensao="html",
    )
