import json
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from concursohub.coletar import MAX_DOCUMENTOS, gerar
from concursohub.texto import FUSO_BR

from .test_cebraspe import cliente_cebraspe
from .util import ClienteFalso, fixture

DIA_1 = datetime(2026, 11, 2, 9, 0, tzinfo=FUSO_BR)
DIA_2 = datetime(2026, 11, 3, 9, 0, tzinfo=FUSO_BR)


class GerarTests(unittest.TestCase):
    def setUp(self):
        self.saida = Path(tempfile.mkdtemp(prefix="concursohub-teste-"))
        self.addCleanup(shutil.rmtree, self.saida, ignore_errors=True)

    def concursos(self) -> dict:
        dados = json.loads((self.saida / "concursos.json").read_text(encoding="utf-8"))
        return {c["id"]: c for c in dados["concursos"]}

    def test_gera_json_classificado(self):
        status = gerar(["cebraspe"], self.saida, {"cebraspe": cliente_cebraspe()}, DIA_1)
        self.assertEqual(status["fontes"]["cebraspe"], {"ok": True, "concursos": 2, "erro": ""})
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
        gerar(["cebraspe"], self.saida, {"cebraspe": cliente_cebraspe(json.dumps(sem_tj).encode())}, DIA_1)
        # O acervo da primeira coleta não é novidade.
        self.assertIsNone(self.concursos()["cebraspe:CGU_26_AFFC"]["primeiro_visto"])

        gerar(["cebraspe"], self.saida, {"cebraspe": cliente_cebraspe()}, DIA_2)
        concursos = self.concursos()
        self.assertEqual(concursos["cebraspe:TJ_CE_25_NOTARIOS"]["primeiro_visto"], "2026-11-03")
        self.assertIsNone(concursos["cebraspe:CGU_26_AFFC"]["primeiro_visto"])

    def test_falha_mantem_dados_anteriores(self):
        gerar(["cebraspe"], self.saida, {"cebraspe": cliente_cebraspe()}, DIA_1)
        with self.assertLogs("concursohub.coletar", "ERROR"):
            status = gerar(["cebraspe"], self.saida, {"cebraspe": ClienteFalso({})}, DIA_2)
        self.assertFalse(status["fontes"]["cebraspe"]["ok"])
        self.assertIn("404", status["fontes"]["cebraspe"]["erro"])
        self.assertEqual(len(self.concursos()), 2)

    def test_fonte_que_nao_rodou_fica_como_estava(self):
        gerar(["cebraspe"], self.saida, {"cebraspe": cliente_cebraspe()}, DIA_1)
        vazia = ClienteFalso({"https://conhecimento.fgv.br/concursos?page=0": b"<html></html>"})
        gerar(["fgv"], self.saida, {"fgv": vazia}, DIA_2)
        self.assertEqual(len(self.concursos()), 2)

    def test_sem_mudanca_nao_reescreve(self):
        gerar(["cebraspe"], self.saida, {"cebraspe": cliente_cebraspe()}, DIA_1)
        arquivo = self.saida / "concursos.json"
        arquivo.write_text(arquivo.read_text(encoding="utf-8") + " ", encoding="utf-8")  # marca
        gerar(["cebraspe"], self.saida, {"cebraspe": cliente_cebraspe()}, DIA_2)
        self.assertTrue(arquivo.read_text(encoding="utf-8").endswith(" "))

    def test_limite_de_documentos(self):
        detalhe = json.loads(cliente_cebraspe().respostas[
            "https://apis.cebraspe.org.br/cebraspe/eventos/CGU_26_AFFC"
        ])
        modelo = next(a for a in detalhe["arquivosEdital"] if a["nomeArquivo"].endswith(".pdf"))
        detalhe["arquivosEdital"] = [dict(modelo, nomeArquivo=f"{n}.pdf") for n in range(MAX_DOCUMENTOS + 5)]
        cliente = cliente_cebraspe()
        cliente.respostas["https://apis.cebraspe.org.br/cebraspe/eventos/CGU_26_AFFC"] = json.dumps(detalhe).encode()
        gerar(["cebraspe"], self.saida, {"cebraspe": cliente}, DIA_1)
        cgu = self.concursos()["cebraspe:CGU_26_AFFC"]
        self.assertEqual((len(cgu["documentos"]), cgu["total_documentos"]), (MAX_DOCUMENTOS, MAX_DOCUMENTOS + 5))
