"""Extração de texto de PDF. PDFs escaneados (imagem) voltam vazios e são
marcados para revisão; OCR com Tesseract pode ser plugado aqui depois.

Usa pypdfium2, 50–80x mais rápido que pdfplumber com o mesmo texto (medido em
PDFs reais da FGV em 01/11/2026). O pdfplumber fica de reserva para PDFs que o
pdfium não abre, e continua sendo a escolha para extrair tabelas.
"""
import io
import logging

log = logging.getLogger(__name__)


def extrair_texto_pdf(conteudo: bytes, max_paginas: int = 200) -> str:
    try:
        return _com_pdfium(conteudo, max_paginas)
    except Exception as erro:
        log.info("pdfium não leu o PDF (%s); tentando pdfplumber", erro)
    try:
        return _com_pdfplumber(conteudo, max_paginas)
    except Exception as erro:  # PDF corrompido ou protegido
        log.warning("Falha ao extrair texto do PDF: %s", erro)
        return ""


def _com_pdfium(conteudo: bytes, max_paginas: int) -> str:
    import pypdfium2 as pdfium

    documento = pdfium.PdfDocument(conteudo)
    try:
        partes = []
        for indice in range(min(len(documento), max_paginas)):
            pagina = documento[indice]
            texto = pagina.get_textpage()
            partes.append(texto.get_text_range())
            texto.close()
            pagina.close()
        # pdfium separa linhas com \r\n; normaliza para \n.
        return "\n".join(partes).replace("\r\n", "\n").replace("\r", "\n").strip()
    finally:
        documento.close()


def _com_pdfplumber(conteudo: bytes, max_paginas: int) -> str:
    import pdfplumber

    partes = []
    with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
        for pagina in pdf.pages[:max_paginas]:
            partes.append(pagina.extract_text() or "")
    return "\n".join(partes).strip()
