from django.test import SimpleTestCase

from ingestao.pdf import extrair_texto_pdf


def pdf_minimo(*linhas: str) -> bytes:
    """PDF de uma página com as linhas em Helvetica, com xref correta."""
    conteudo = "BT /F1 12 Tf 72 720 Td 14 TL " + " ".join(f"({linha}) '" for linha in linhas) + " ET"
    objetos = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        " /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(conteudo)} >>\nstream\n{conteudo}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    saida = b"%PDF-1.4\n"
    posicoes = []
    for numero, objeto in enumerate(objetos, start=1):
        posicoes.append(len(saida))
        saida += f"{numero} 0 obj\n{objeto}\nendobj\n".encode("latin-1")
    inicio_xref = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    saida += "".join(f"{p:010d} 00000 n \n" for p in posicoes).encode()
    saida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n".encode()
    return saida


class ExtrairTextoPdfTests(SimpleTestCase):
    def test_extrai_texto_com_quebras_de_linha_normalizadas(self):
        texto = extrair_texto_pdf(pdf_minimo("EDITAL N 1", "Cargo: Analista de TI"))
        self.assertIn("EDITAL N 1", texto)
        self.assertIn("Cargo: Analista de TI", texto)
        self.assertNotIn("\r", texto)

    def test_pdf_invalido_volta_vazio(self):
        self.assertEqual(extrair_texto_pdf(b"%PDF-1.4 conteudo de teste"), "")
