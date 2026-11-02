"""Leitura de editais com trechos reais (tests/fixtures/editais/, recortados em 02/11/2026)."""
import unittest
from datetime import datetime
from decimal import Decimal

from concursohub.adaptadores.base import DocumentoExtraido
from concursohub.areas import areas_do_cargo
from concursohub.coletar import tipo_do_documento
from concursohub.edital import analisar, escolher_edital, remuneracao_unica, texto_do_pdf
from concursohub.texto import FUSO_BR

from .util import fixture


def edital(nome: str) -> str:
    return fixture(f"editais/{nome}.txt").decode("utf-8")


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


class CebraspeEditalTests(unittest.TestCase):
    def test_remuneracao_por_cargo(self):
        # TCE-MS 25: cargo 1 tem a sua; cargos 2 a 5 herdam a do grupo "DOS CARGOS DE AUDITOR".
        cargos = analisar(edital("cebraspe_tcems25"))
        self.assertEqual(
            [(c.numero, c.remuneracao) for c in cargos],
            [(1, Decimal("10352.75"))] + [(n, Decimal("14232.67")) for n in range(2, 6)],
        )
        self.assertEqual(cargos[1].nome, "AUDITOR DE CONTROLE EXTERNO – ÁREA: CIÊNCIAS CONTÁBEIS")

    def test_subsidio_antes_do_grupo_e_nome_quebrado(self):
        # CGU 26: "SUBSÍDIO INICIAL" uma vez, antes dos cargos 1 a 4; nomes em duas linhas.
        cargos = analisar(edital("cebraspe_cgu26"))
        self.assertEqual([c.remuneracao for c in cargos], [Decimal("20000.00")] * 4)
        self.assertEqual(
            cargos[1].nome,
            "AUDITOR FEDERAL DE FINANÇAS E CONTROLE (AFFC) – ESPECIALIDADE: TECNOLOGIA DA INFORMAÇÃO – CIÊNCIA DE DADOS",
        )

    def test_grupos_com_remuneracoes_diferentes(self):
        # UDESC 26: cargos 1-10 no grupo de nível superior, 11-12 no de nível médio (texto com espaço não separável).
        cargos = analisar(edital("cebraspe_udesc26"))
        self.assertEqual(len(cargos), 12)
        self.assertEqual({c.remuneracao for c in cargos[:10]}, {Decimal("6858.78")})
        self.assertEqual({c.remuneracao for c in cargos[10:]}, {Decimal("4921.46")})

    def test_edital_de_um_cargo(self):
        texto = edital("cebraspe_pcma26")
        self.assertEqual(analisar(texto), [])
        self.assertEqual(remuneracao_unica(texto), Decimal("22820.23"))


class FgvEditalTests(unittest.TestCase):
    def test_quadro_com_perfis_e_anexo_de_remuneracao(self):
        # Dataprev 26: perfis quebrados em várias linhas, uma linha por cidade, e a
        # remuneração no Anexo III ("Analista de TI (Todos os perfis)").
        cargos = analisar(edital("fgv_dataprev26"))
        nomes = [c.nome for c in cargos]
        self.assertEqual(len(cargos), 13)
        for nome in ("ANÁLISE DE NEGÓCIO DE TI", "ADVOCACIA", "CONTABILIDADE", "GESTÃO ECONÔMICO-FINANCEIRA",
                     "ENGENHARIA", "ANALISTA DE PROCESSAMENTO"):
            self.assertIn(nome, nomes)
        salarios = {c.nome: c.remuneracao for c in cargos}
        self.assertEqual(salarios["ANALISTA DE PROCESSAMENTO"], Decimal("8273.94"))
        self.assertEqual({v for n, v in salarios.items() if n != "ANALISTA DE PROCESSAMENTO"}, {Decimal("10685.44")})

    def test_quadro_com_vencimento_na_linha(self):
        cargos = analisar(edital("fgv_tjpb26"))
        self.assertEqual(len(cargos), 9)
        self.assertEqual(cargos[1].nome, "ANALISTA – TI – Desenvolvimento de Sistemas")
        self.assertEqual({c.remuneracao for c in cargos}, {Decimal("7526.14")})

    def test_quadro_sem_remuneracao(self):
        cargos = analisar(edital("fgv_aleam25"))
        nomes = [c.nome for c in cargos]
        self.assertIn("Analista de Redes de Comunicação de Dados", nomes)
        self.assertIn("Contador", nomes)
        self.assertTrue(all(c.remuneracao is None for c in cargos))

    def test_valor_sem_cifrao_e_localidade_quebrada(self):
        # NAV Brasil 26: coluna "Remuneração (R$)" sem o "R$" no valor, e a cidade
        # quebrada em duas linhas ("Rio de Janeiro -" / "RJ 4.632,10").
        cargos = {c.nome: c.remuneracao for c in analisar(edital("fgv_navbrasil26"))}
        self.assertEqual(cargos["Assistente Social"], Decimal("4632.10"))
        self.assertEqual(cargos["Advogado"], Decimal("6186.00"))
        self.assertEqual(cargos["Engenheiro Civil"], Decimal("10868.68"))
        self.assertFalse(any("RJ" in nome or "S.A." in nome for nome in cargos))

    def test_quadro_em_anexo_com_linhas_por_uf(self):
        # MPU 25: o quadro está no "ANEXO VII – DISTRIBUIÇÃO DE VAGAS POR UF", com uma linha por UF.
        nomes = [c.nome for c in analisar(edital("fgv_mpu25_anexo"))]
        self.assertEqual(nomes[:2], ["Analista do MPU – Direito", "Técnico do MPU – Administração"])
        self.assertIn("Técnico do MPU - Polícia Institucional", nomes)

    def test_quadro_com_regioes_e_classe(self):
        nomes = [c.nome for c in analisar(edital("fgv_dpero25"))]
        self.assertIn("TÉCNICO DA DEFENSORIA PÚBLICA – Técnico em Informática", nomes)
        self.assertIn("ANALISTA DA DEFENSORIA PÚBLICA – Analista Jurídico", nomes)
        self.assertFalse(any("Região" in n or "Classe" in n for n in nomes))


class AreasDosCargosTests(unittest.TestCase):
    def test_dataprev_tem_varias_areas(self):
        areas = {c.nome: areas_do_cargo(c.nome) for c in analisar(edital("fgv_dataprev26"))}
        self.assertEqual(areas["ADVOCACIA"], ["Jurídica"])
        self.assertEqual(areas["CONTABILIDADE"], ["Contabilidade e Economia"])
        self.assertEqual(areas["ENGENHARIA"], ["Engenharia"])
        self.assertEqual(areas["ARQUITETURA, ENGENHARIA E SUSTENTAÇÃO TECNOLÓGICA"], ["TI"])
        self.assertEqual(areas["DESENVOLVIMENTO DE SOFTWARE"], ["TI"])

    def test_perfil_decide_e_carreira_continua(self):
        casos = {
            # O perfil manda: é vaga de advogado, não de TI.
            "ANALISTA DE TECNOLOGIA DA INFORMAÇÃO – PERFIL: 7. ADVOCACIA": ["Jurídica"],
            # Carreira (Controle, Legislativo) continua junto com o perfil.
            "AUDITOR FEDERAL DE FINANÇAS E CONTROLE (AFFC) – ESPECIALIDADE: TECNOLOGIA DA INFORMAÇÃO": ["Controle", "TI"],
            "ANALISTA LEGISLATIVO – ESPECIALIDADE: ENGENHEIRO – ÁREA: ENGENHARIA CIVIL": ["Engenharia", "Legislativo"],
            "AUDITOR DE CONTROLE EXTERNO – ÁREA: CIÊNCIAS CONTÁBEIS": ["Contabilidade e Economia", "Controle"],
            # Perfil sem área conhecida: fica a do nome.
            "AUDITOR FEDERAL DE FINANÇAS E CONTROLE (AFFC) – ESPECIALIDADE: AUDITORIA": ["Controle"],
            # "Defensoria" no nome do cargo não faz dele defensor público.
            "TÉCNICO DA DEFENSORIA PÚBLICA – Técnico em Informática": ["TI"],
        }
        for nome, esperadas in casos.items():
            with self.subTest(nome=nome):
                self.assertEqual(areas_do_cargo(nome), esperadas)


class EscolherEditalTests(unittest.TestCase):
    def doc(self, titulo, dia=1, url=None):
        return DocumentoExtraido(
            titulo=titulo, url=url or f"https://x/{titulo}.pdf", publicado_em=datetime(2026, 10, dia, tzinfo=FUSO_BR)
        )

    def test_consolidado_vence_original(self):
        docs = [self.doc("Edital nº 1 - Abertura"), self.doc("Edital nº 1 - Abertura - Atualizado conforme retificações")]
        self.assertEqual(escolher_edital(docs, tipo_do_documento).titulo, docs[1].titulo)

    def test_ignora_o_que_so_cita_o_edital(self):
        # Casos reais: MRE 23 e TJ-RO 25 tinham estes documentos mais novos que o edital.
        docs = [
            self.doc("Edital nº 1 – Abertura", 1),
            self.doc("Resposta às impugnações do edital de abertura", 9),
            self.doc("Relação dos candidatos que se enquadram na hipótese prevista no edital nº 1", 9),
        ]
        self.assertEqual(escolher_edital(docs, tipo_do_documento).titulo, "Edital nº 1 – Abertura")

    def test_sem_edital(self):
        self.assertIsNone(escolher_edital([self.doc("Gabarito preliminar")], tipo_do_documento))


class TextoDoPdfTests(unittest.TestCase):
    def test_extrai_texto(self):
        texto = texto_do_pdf(pdf_minimo("2.1 CARGO 1: ANALISTA DE SISTEMAS", "REMUNERACAO: R$ 9.000,00"))
        self.assertIn("CARGO 1: ANALISTA DE SISTEMAS", texto)
        self.assertNotIn("\r", texto)
        self.assertEqual(analisar(texto)[0].remuneracao, Decimal("9000.00"))
