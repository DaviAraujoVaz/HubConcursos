import json
import unittest
from decimal import Decimal

from concursohub.adaptadores.cebraspe import URL_DETALHE, URL_LISTA, CebraspeAdaptador, converter
from concursohub.areas import areas_do_concurso
from concursohub.coletar import tipo_do_documento
from concursohub.inferencia import inferir_esfera
from concursohub.modelos import Situacao, TipoDocumento

from .util import ClienteFalso, fixture


def cliente_cebraspe(lista=None, encerrado=False):
    respostas = {
        URL_LISTA: lista or fixture("cebraspe_lista.json"),
        URL_DETALHE.format(slug="CGU_26_AFFC"): fixture("cebraspe_detalhe_cgu.json"),
        URL_DETALHE.format(slug="TJ_CE_25_NOTARIOS"): json.dumps(
            {"eventoURL": "TJ_CE_25_NOTARIOS", "eventoCargos": [], "arquivosEdital": []}
        ).encode(),
    }
    if encerrado:
        respostas[URL_DETALHE.format(slug="PF_21")] = json.dumps({"eventoURL": "PF_21"}).encode()
    return ClienteFalso(respostas)


class ConverterCebraspeTests(unittest.TestCase):
    def test_converte_detalhe(self):
        evento = json.loads(fixture("cebraspe_lista.json"))[1]["eventos"][0]
        detalhe = json.loads(fixture("cebraspe_detalhe_cgu.json"))
        c = converter(evento, detalhe)

        self.assertEqual(c.chave_externa, "cebraspe:CGU_26_AFFC")
        self.assertEqual(c.situacao, Situacao.ABERTO)
        self.assertEqual(c.vagas_total, 60)
        self.assertEqual(c.remuneracao_maxima, Decimal("20000"))
        self.assertEqual((c.inscricoes_inicio.day, c.inscricoes_inicio.month), (10, 10))
        self.assertEqual((c.inscricoes_fim.day, c.inscricoes_fim.month, c.inscricoes_fim.hour), (4, 11, 18))
        self.assertEqual(c.cargos[0].nome, "AUDITOR FEDERAL DE FINANÇAS E CONTROLE (AFFC) – ESPECIALIDADE: AUDITORIA")
        # Versões HTML (VLibras) ficam de fora; só os 4 PDFs entram.
        self.assertEqual(len(c.documentos), 4)
        self.assertTrue(all(d.url.endswith(".pdf") for d in c.documentos))

    def test_titulo_ignora_nome_completo_igual_ao_slug(self):
        # Caso real (ADEAL, 29/10/2026): eventoNomeCompleto vem igual à URL.
        evento = {"eventoURL": "ADEAL_26", "eventoNomeAbreviado": "ADEAL 26", "eventoStatus": "em-andamento"}
        detalhe = {"eventoURL": "ADEAL_26", "eventoNomeAbreviado": "ADEAL 26", "eventoNomeCompleto": "ADEAL_26"}
        self.assertEqual(converter(evento, detalhe).titulo, "ADEAL 26")
        self.assertEqual(converter({"eventoURL": "X_26"}, {}).titulo, "X 26")

    def test_pf25_dados_reais(self):
        """Amostra fiel da API real (PF 25, capturada em 29/10/2026)."""
        dados = json.loads(fixture("cebraspe_real_pf25.json"))
        c = converter(dados["evento"], dados["detalhe"])
        self.assertEqual(c.situacao, Situacao.ANDAMENTO)
        self.assertEqual(c.cargos[0].nome, "Delegado de Polícia Federal")
        self.assertEqual(len(c.documentos), 8)
        self.assertEqual(inferir_esfera(c.titulo), "federal")
        self.assertEqual(areas_do_concurso(c.titulo, [cargo.nome for cargo in c.cargos]), ["Policial", "TI"])

        tipos = {d.titulo.split(" - ")[0].split(" – ")[0]: tipo_do_documento(d) for d in c.documentos}
        self.assertEqual(tipos["Edital nº 48"], TipoDocumento.RETIFICACAO)
        self.assertEqual(tipos["Edital nº 47"], TipoDocumento.CONVOCACAO)
        self.assertEqual(tipos["Edital nº 45"], TipoDocumento.HOMOLOGACAO)
        self.assertEqual(tipos["Edital nº 42"], TipoDocumento.RESULTADO)
        self.assertEqual(tipos["Edital nº 4"], TipoDocumento.CONVOCACAO)
        self.assertEqual(tipos["Comunicado"], TipoDocumento.COMUNICADO)
        self.assertEqual(tipos["PADRÃO DEFINITIVO DE RESPOSTAS"], TipoDocumento.GABARITO)


class ColetaCebraspeTests(unittest.TestCase):
    def test_so_ativos_por_padrao(self):
        cliente = cliente_cebraspe()
        concursos = list(CebraspeAdaptador(cliente).coletar())
        # Encerrados ficam de fora: novo + inscrições abertas.
        self.assertEqual(sorted(c.chave_externa for c in concursos), ["cebraspe:CGU_26_AFFC", "cebraspe:TJ_CE_25_NOTARIOS"])
        self.assertNotIn(URL_DETALHE.format(slug="PF_21"), cliente.pedidos)

    def test_incluir_encerrados(self):
        concursos = list(CebraspeAdaptador(cliente_cebraspe(encerrado=True)).coletar(incluir_encerrados=True))
        pf = next(c for c in concursos if c.chave_externa == "cebraspe:PF_21")
        self.assertEqual(pf.situacao, Situacao.ENCERRADO)
