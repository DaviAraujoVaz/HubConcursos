"""Extração de texto de PDF. PDFs escaneados (imagem) voltam vazios e são
marcados para revisão; OCR com Tesseract pode ser plugado aqui depois."""
import io
import logging

log = logging.getLogger(__name__)


def extrair_texto_pdf(conteudo: bytes, max_paginas: int = 200) -> str:
    try:
        import pdfplumber
    except ImportError:  # pragma: no cover
        log.warning("pdfplumber não instalado; texto do PDF não extraído")
        return ""
    try:
        partes = []
        with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
            for pagina in pdf.pages[:max_paginas]:
                partes.append(pagina.extract_text() or "")
        return "\n".join(partes).strip()
    except Exception as erro:  # PDF corrompido ou protegido
        log.warning("Falha ao extrair texto do PDF: %s", erro)
        return ""
