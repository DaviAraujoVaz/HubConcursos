import json
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from concursohub.adaptadores.cebraspe import URL_ARQUIVO
from concursohub.coletar import MAX_DOCUMENTOS, gerar
from concursohub.texto import FUSO_BR

from .test_cebraspe import cliente_cebraspe
from .test_edital import pdf_minimo
from .util import ClienteFalso, fixture

DIA_1 = datetime(2026, 11, 2, 9, 0, tzinfo=FUSO_BR)
DIA_2 = datetime(2026, 11, 3, 9, 0, tzinfo=FUSO_BR)


class GerarTests(unittest.TestCase):
    def setUp(self):
        self.saida = Path(tempfile.mkdtemp(prefix="concursohub-teste-"))
        self.addCleanup(shutil.rmtree, self.saida, ignore_errors=True)

    def gerar(self, fontes, clientes, agora, baixar_editais=False):
        return gerar(fontes, self.saida, clientes, agora, self.saida / "editais.json", baixar_editais)

    def concursos(self) -> dict:
        dados = json.loads((self.saida / "concursos.json").read_text(encoding="utf-8"))
        return {c["id"]: c for c in dados["concursos"]}

    def test_gera_json_classificado(self):
        status = self.gerar(["cebraspe"], {"cebraspe": cliente_cebraspe()}, DIA_1)
        self.assertEqual(status["fontes"]["cebraspe"], {"ok": True, "concursos": 2, "com_cargos": 1, "erro": ""})
        cgu = self.concursos()["cebraspe:CGU_26_AFFC"]
        self.assertEqual(cgu["situacao"], "aberto")
        self.assertEqual(cgu["esfera"], "federal")
        self.assertEqual(cgu["areas"], ["Controle", "TI"])
        self.assertEqual(cgu["inscricoes_fim"], "2026-11-04T18:00-03:00")
        self.assertEqual(cgu["vagas"], 60)
        self.assertEqual(cgu["total_documentos"], 4)
        # Documentos do mais novo para o mais antigo, já com o tipo.
        datas = [d["data"] for d in cgu["documentos"]]
        self.assertEqual(datas, sorted(datas, reverse=True))
        self.assertIn("retificacao", {d["tipo"] for d in cgu["documentos"]})
        status_salvo = json.loads((self.saida / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(status_salvo["gerado_em"], "2026-11-02T09:00-03:00")

    def test_primeiro_visto_so_depois_da_primeira_coleta(self):
        lista = json.loads(fixture("cebraspe_lista.json"))
        sem_tj = [dict(fase, eventos=[e for e in fase["eventos"] if e["eventoURL"] != "TJ_CE_25_NOTARIOS"]) for fase in lista]
        self.gerar(["cebraspe"], {"cebraspe": cliente_cebraspe(json.dumps(sem_tj).encode())}, DIA_1)
        # O acervo da primeira coleta não é novidade.
        self.assertIsNone(self.concursos()["cebraspe:CGU_26_AFFC"]["primeiro_visto"])

        self.gerar(["cebraspe"], {"cebraspe": cliente_cebraspe()}, DIA_2)
        concursos = self.concursos()
        self.assertEqual(concursos["cebraspe:TJ_CE_25_NOTARIOS"]["primeiro_visto"], "2026-11-03")
        self.assertIsNone(concursos["cebraspe:CGU_26_AFFC"]["primeiro_visto"])

    def test_falha_mantem_dados_anteriores(self):
        self.gerar(["cebraspe"], {"cebraspe": cliente_cebraspe()}, DIA_1)
        with self.assertLogs("concursohub.coletar", "ERROR"):
            status = self.gerar(["cebraspe"], {"cebraspe": ClienteFalso({})}, DIA_2)
        self.assertFalse(status["fontes"]["cebraspe"]["ok"])
        self.assertIn("404", status["fontes"]["cebraspe"]["erro"])
        self.assertEqual(len(self.concursos()), 2)

    def test_fonte_que_nao_rodou_fica_como_estava(self):
        self.gerar(["cebraspe"], {"cebraspe": cliente_cebraspe()}, DIA_1)
        vazia = ClienteFalso({"https://conhecimento.fgv.br/concursos?page=0": b"<html></html>"})
        self.gerar(["fgv"], {"fgv": vazia}, DIA_2)
        self.assertEqual(len(self.concursos()), 2)

    def test_sem_mudanca_nao_reescreve(self):
        self.gerar(["cebraspe"], {"cebraspe": cliente_cebraspe()}, DIA_1)
        arquivo = self.saida / "concursos.json"
        arquivo.write_text(arquivo.read_text(encoding="utf-8") + " ", encoding="utf-8")  # marca
        self.gerar(["cebraspe"], {"cebraspe": cliente_cebraspe()}, DIA_2)
        self.assertTrue(arquivo.read_text(encoding="utf-8").endswith(" "))

    def test_limite_de_documentos(self):
        detalhe = json.loads(cliente_cebraspe().respostas[
            "https://apis.cebraspe.org.br/cebraspe/eventos/CGU_26_AFFC"
        ])
        modelo = next(a for a in detalhe["arquivosEdital"] if a["nomeArquivo"].endswith(".pdf"))
        detalhe["arquivosEdital"] = [dict(modelo, nomeArquivo=f"{n}.pdf") for n in range(MAX_DOCUMENTOS + 5)]
        cliente = cliente_cebraspe()
        cliente.respostas["https://apis.cebraspe.org.br/cebraspe/eventos/CGU_26_AFFC"] = json.dumps(detalhe).encode()
        self.gerar(["cebraspe"], {"cebraspe": cliente}, DIA_1)
        cgu = self.concursos()["cebraspe:CGU_26_AFFC"]
        self.assertEqual((len(cgu["documentos"]), cgu["total_documentos"]), (MAX_DOCUMENTOS, MAX_DOCUMENTOS + 5))

    def test_cargos_e_salarios_do_edital(self):
        cliente = cliente_cebraspe()
        pdf = pdf_minimo(
            "2.1 CARGO 1: AUDITOR FEDERAL DE FINANCAS E CONTROLE - ESPECIALIDADE: AUDITORIA",
            "REMUNERACAO: R$ 20.000,00",
            "2.2 CARGO 2: AUDITOR FEDERAL DE FINANCAS E CONTROLE - ESPECIALIDADE: TI",
            "REMUNERACAO: R$ 21.000,00",
        )
        url_edital = URL_ARQUIVO.format(slug="CGU_26_AFFC", arquivo="FDEEFB41.pdf")  # o "Atualizado"
        cliente.respostas[url_edital] = pdf
        self.gerar(["cebraspe"], {"cebraspe": cliente}, DIA_1, baixar_editais=True)

        cgu = self.concursos()["cebraspe:CGU_26_AFFC"]
        self.assertEqual([c["remuneracao"] for c in cgu["cargos"]], [20000.0, 21000.0])
        self.assertEqual(cgu["cargos"][1]["areas"], ["Controle", "TI"])
        cache = json.loads((self.saida / "editais.json").read_text(encoding="utf-8"))
        self.assertEqual(list(cache), [url_edital])

        # Edital já lido não é baixado de novo.
        cliente = cliente_cebraspe()
        self.gerar(["cebraspe"], {"cebraspe": cliente}, DIA_2, baixar_editais=True)
        self.assertNotIn(url_edital, cliente.pedidos)
        self.assertEqual(self.concursos()["cebraspe:CGU_26_AFFC"]["cargos"][1]["remuneracao"], 21000.0)

    def test_edital_fora_do_ar_nao_derruba_a_coleta(self):
        with self.assertLogs("concursohub.coletar", "WARNING"):
            status = self.gerar(["cebraspe"], {"cebraspe": cliente_cebraspe()}, DIA_1, baixar_editais=True)
        self.assertTrue(status["fontes"]["cebraspe"]["ok"])
        cache = json.loads((self.saida / "editais.json").read_text(encoding="utf-8"))
        self.assertIn("404", next(iter(cache.values()))["erro"])
