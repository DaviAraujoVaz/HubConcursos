"""DOU pelo INLABS (Imprensa Nacional) — edições completas em XML, grátis.

Precisa de conta gratuita em https://inlabs.in.gov.br (INLABS_EMAIL / INLABS_SENHA).
Download segue o script oficial (github.com/Imprensa-Nacional/inlabs):
  POST https://inlabs.in.gov.br/logar.php  (email, password) → cookie inlabs_session_cookie
  GET  https://inlabs.in.gov.br/index.php?p=AAAA-MM-DD&dl=AAAA-MM-DD-DO3.zip
Cada ZIP traz um XML por matéria, no formato <xml><article …atributos…><body>
<Identifica/><Ementa/><Texto/></body></article></xml>. O parser abaixo é tolerante
a variações (nomes de tags sem diferenciar maiúsculas, atributos ausentes).

O DOU entra como fluxo de *documentos* (autorizações, editais, homologações…),
ainda sem concurso vinculado: você vincula no admin, ou uma regra futura faz isso.
"""
import io
import logging
import zipfile
from datetime import date, timedelta

from bs4 import BeautifulSoup
from django.conf import settings
from lxml import etree

from ..classificador import classificar_tipo, eh_ato_de_concurso
from ..texto import limpar_espacos, parse_data_br
from .base import Adaptador, DocumentoExtraido, ResultadoColeta, registrar

log = logging.getLogger(__name__)

URL_LOGIN = "https://inlabs.in.gov.br/logar.php"
URL_DOWNLOAD = "https://inlabs.in.gov.br/index.php?p={data}&dl={data}-{secao}.zip"
URL_MATERIA = "https://www.in.gov.br/web/dou/-/{nome}"
SECOES_PADRAO = ("DO1", "DO2", "DO3", "DO1E", "DO2E", "DO3E")


class InlabsSemCredenciais(RuntimeError):
    pass


@registrar
class DouAdaptador(Adaptador):
    slug = "dou"
    nome = "Diário Oficial da União (INLABS)"

    def entrar(self):
        if not (settings.INLABS_EMAIL and settings.INLABS_SENHA):
            raise InlabsSemCredenciais("Defina INLABS_EMAIL e INLABS_SENHA no .env (conta gratuita no INLABS).")
        self.cliente.post(
            URL_LOGIN,
            data={"email": settings.INLABS_EMAIL, "password": settings.INLABS_SENHA},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if not self.cliente.sessao.cookies.get("inlabs_session_cookie"):
            raise RuntimeError("Login no INLABS falhou: confira e-mail e senha.")

    def baixar_zip(self, dia: date, secao: str) -> bytes | None:
        data = dia.isoformat()
        cookie = self.cliente.sessao.cookies.get("inlabs_session_cookie")
        try:
            resposta = self.cliente.get(
                URL_DOWNLOAD.format(data=data, secao=secao),
                headers={"Cookie": f"inlabs_session_cookie={cookie}", "origem": "736372697074"},
            )
        except Exception as erro:
            status = getattr(getattr(erro, "response", None), "status_code", None)
            if status == 404:
                return None  # edição/seção inexistente no dia (ex.: extra)
            raise
        return resposta.content or None

    def coletar(self, data_inicio: date | None = None, data_fim: date | None = None, secoes=SECOES_PADRAO, **_):
        hoje = date.today()
        data_fim = data_fim or hoje
        data_inicio = data_inicio or data_fim
        self.entrar()
        dia = data_inicio
        while dia <= data_fim:
            documentos = []
            for secao in secoes:
                conteudo = self.baixar_zip(dia, secao)
                if not conteudo:
                    continue
                documentos.extend(documentos_de_concurso(conteudo))
            log.info("DOU %s: %d atos sobre concurso", dia.isoformat(), len(documentos))
            yield ResultadoColeta(documentos_soltos=documentos)
            dia += timedelta(days=1)


def _filho(elemento, nome: str):
    """Primeiro descendente com a tag `nome`, sem diferenciar maiúsculas."""
    alvo = nome.lower()
    for filho in elemento.iter():
        if isinstance(filho.tag, str) and filho.tag.lower() == alvo:
            return filho
    return None


def _texto_html(elemento) -> str:
    if elemento is None:
        return ""
    bruto = " ".join(elemento.itertext())
    return limpar_espacos(BeautifulSoup(bruto, "lxml").get_text(" ")) if "<" in bruto else limpar_espacos(bruto)


def parse_materias(xml: bytes) -> list[dict]:
    """Lê um XML do INLABS e devolve as matérias como dicionários simples."""
    parser = etree.XMLParser(recover=True, huge_tree=True)
    raiz = etree.fromstring(xml, parser=parser)
    if raiz is None:
        return []
    artigos = [el for el in raiz.iter() if isinstance(el.tag, str) and el.tag.lower() == "article"]
    materias = []
    for artigo in artigos:
        atributos = {k: v for k, v in artigo.attrib.items()}
        texto = _texto_html(_filho(artigo, "Texto"))
        materias.append(
            {
                "id": atributos.get("idMateria") or atributos.get("id") or "",
                "nome": atributos.get("name") or "",
                "secao": atributos.get("pubName") or "",
                "tipo_ato": atributos.get("artType") or "",
                "categoria": atributos.get("artCategory") or "",
                "data": atributos.get("pubDate") or "",
                "pdf": atributos.get("pdfPage") or "",
                "identifica": _texto_html(_filho(artigo, "Identifica")),
                "ementa": _texto_html(_filho(artigo, "Ementa")),
                "texto": texto,
                "atributos": atributos,
            }
        )
    return materias


def documentos_de_concurso(conteudo_zip: bytes) -> list[DocumentoExtraido]:
    documentos = []
    with zipfile.ZipFile(io.BytesIO(conteudo_zip)) as pacote:
        for nome in pacote.namelist():
            if not nome.lower().endswith(".xml"):
                continue
            xml = pacote.read(nome)
            for materia in parse_materias(xml):
                if not eh_ato_de_concurso(materia["identifica"], materia["ementa"], materia["texto"][:3000]):
                    continue
                documentos.append(_converter(materia, xml))
    return documentos


def _converter(materia: dict, xml: bytes) -> DocumentoExtraido:
    titulo = materia["identifica"] or materia["tipo_ato"] or materia["nome"]
    orgao = materia["categoria"].split("/")[-1] if materia["categoria"] else ""
    titulo_completo = f"{titulo} — {orgao}" if orgao else titulo
    # pdfPage aponta para a página oficial da edição; é o link mais estável que o XML traz.
    url = materia["pdf"] or (URL_MATERIA.format(nome=materia["nome"]) if materia["nome"] else "")
    return DocumentoExtraido(
        chave_externa=f"materia:{materia['id'] or materia['nome']}",
        titulo=titulo_completo,
        url=url,
        tipo=classificar_tipo(f"{titulo} {materia['ementa']}", materia["texto"]),
        publicado_em=parse_data_br(materia["data"]),
        extensao="xml",
        texto=materia["texto"],
        conteudo=xml,
        metadados={
            "secao": materia["secao"],
            "tipo_ato": materia["tipo_ato"],
            "orgao_hierarquia": materia["categoria"],
            "ementa": materia["ementa"],
            "pdf": materia["pdf"],
        },
    )
