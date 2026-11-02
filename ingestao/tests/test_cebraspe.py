import json
from decimal import Decimal

from catalogo.models import Concurso, Situacao
from ingestao.adaptadores.cebraspe import URL_ARQUIVO, URL_DETALHE, URL_LISTA, CebraspeAdaptador, converter
from ingestao.coleta import executar
from ingestao.models import Documento, EventoDominio, Execucao, TipoDocumento

from .util import ClienteFalso, TesteComDados, fixture

PDF_FALSO = b"%PDF-1.4 conteudo de teste"


def cliente_cebraspe(lista=None):
    respostas = {
        URL_LISTA: lista or fixture("cebraspe_lista.json"),
        URL_DETALHE.format(slug="CGU_26_AFFC"): fixture("cebraspe_detalhe_cgu.json"),
        URL_DETALHE.format(slug="TJ_CE_25_NOTARIOS"): json.dumps(
            {"eventoURL": "TJ_CE_25_NOTARIOS", "eventoCargos": [], "arquivosEdital": []}
        ).encode(),
    }
    for nome in ("8CC969EF.pdf", "A26FBD90.pdf", "FDEEFB41.pdf", "C7A60D15.pdf"):
        respostas[URL_ARQUIVO.format(slug="CGU_26_AFFC", arquivo=nome)] = PDF_FALSO + nome.encode()
    return ClienteFalso(respostas)


class ConverterCebraspeTests(TesteComDados):
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


class DadosReaisCebraspeTests(TesteComDados):
    """Amostra fiel da API real (PF 25, capturada em 29/10/2026)."""

    def test_pf25(self):
        from ingestao.adaptadores.base import ResultadoColeta
        from ingestao.models import Fonte
        from ingestao.persistencia import persistir

        dados = json.loads(fixture("cebraspe_real_pf25.json"))
        c = converter(dados["evento"], dados["detalhe"])
        self.assertEqual(c.situacao, Situacao.ANDAMENTO)
        self.assertEqual(c.cargos[0].nome, "Delegado de Polícia Federal")

        tipos = {d.titulo[:20]: d for d in c.documentos}
        self.assertEqual(len(c.documentos), 8)

        persistir(Fonte.objects.get(slug="cebraspe"), CebraspeAdaptador(ClienteFalso({})), ResultadoColeta(concursos=[c]), baixar_arquivos=False)
        pf = Concurso.objects.get(chave_externa="cebraspe:PF_25")
        self.assertEqual(pf.esfera, "federal")
        self.assertEqual(sorted(pf.areas.values_list("nome", flat=True)), ["Policial", "TI"])
        perito_ti = pf.cargos.get(nome__contains="Informática")
        self.assertEqual(sorted(perito_ti.areas.values_list("nome", flat=True)), ["Policial", "TI"])

        tipos = {d.titulo.split(" - ")[0].split(" – ")[0]: d.tipo for d in Documento.objects.filter(concurso=pf)}
        self.assertEqual(tipos["Edital nº 48"], TipoDocumento.RETIFICACAO)
        self.assertEqual(tipos["Edital nº 47"], TipoDocumento.CONVOCACAO)
        self.assertEqual(tipos["Edital nº 45"], TipoDocumento.HOMOLOGACAO)
        self.assertEqual(tipos["Edital nº 42"], TipoDocumento.RESULTADO)
        self.assertEqual(tipos["Edital nº 4"], TipoDocumento.CONVOCACAO)
        self.assertEqual(tipos["Comunicado"], TipoDocumento.COMUNICADO)
        self.assertEqual(tipos["PADRÃO DEFINITIVO DE RESPOSTAS"], TipoDocumento.GABARITO)


class ColetaCebraspeTests(TesteComDados):
    def coletar(self, cliente, **opcoes):
        original = CebraspeAdaptador.__init__

        def init(self_, cliente_=None):
            original(self_, cliente)

        CebraspeAdaptador.__init__ = init
        try:
            return executar("cebraspe", **opcoes)
        finally:
            CebraspeAdaptador.__init__ = original

    def test_coleta_completa_e_idempotente(self):
        cliente = cliente_cebraspe()
        execucao = self.coletar(cliente)

        self.assertEqual(execucao.status, Execucao.Status.OK)
        # Encerrados ficam de fora por padrão: 2 concursos (novo + inscrições abertas).
        self.assertEqual(execucao.concursos_novos, 2)
        self.assertNotIn(URL_DETALHE.format(slug="PF_21"), cliente.pedidos)

        cgu = Concurso.objects.get(chave_externa="cebraspe:CGU_26_AFFC")
        self.assertEqual(cgu.banca.slug, "cebraspe")
        self.assertEqual(cgu.esfera, "federal")
        self.assertEqual(sorted(cgu.areas.values_list("nome", flat=True)), ["Controle", "TI"])
        self.assertEqual(cgu.cargos.count(), 2)

        docs = Documento.objects.filter(concurso=cgu)
        self.assertEqual(docs.count(), 4)
        tipos = dict(docs.values_list("chave_externa", "tipo"))
        self.assertEqual(tipos["CGU_26_AFFC/C7A60D15.pdf"], TipoDocumento.EDITAL_ABERTURA)
        self.assertEqual(tipos["CGU_26_AFFC/FDEEFB41.pdf"], TipoDocumento.EDITAL_ABERTURA)
        self.assertEqual(tipos["CGU_26_AFFC/8CC969EF.pdf"], TipoDocumento.RETIFICACAO)
        self.assertTrue(all(d.sha256 and d.arquivo for d in docs))
        # Primeira coleta da fonte: o acervo entra sem gerar aviso.
        self.assertFalse(EventoDominio.objects.filter(processado_em__isnull=True).exists())

        # Segunda rodada: nada novo, nenhum evento a mais.
        eventos_antes = EventoDominio.objects.count()
        segunda = self.coletar(cliente_cebraspe())
        self.assertEqual((segunda.concursos_novos, segunda.documentos_novos), (0, 0))
        self.assertEqual(EventoDominio.objects.count(), eventos_antes)

    def test_revisado_nao_e_sobrescrito_mas_situacao_atualiza(self):
        self.coletar(cliente_cebraspe())
        cgu = Concurso.objects.get(chave_externa="cebraspe:CGU_26_AFFC")
        cgu.titulo = "CGU 2026 — Auditor Federal de Finanças e Controle"
        cgu.revisado = True
        cgu.save()

        lista = json.loads(fixture("cebraspe_lista.json"))
        evento = lista[1]["eventos"].pop()
        evento["eventoStatus"] = "em-andamento"
        lista[2]["eventos"].append(evento)
        self.coletar(cliente_cebraspe(json.dumps(lista).encode()))

        cgu.refresh_from_db()
        self.assertEqual(cgu.titulo, "CGU 2026 — Auditor Federal de Finanças e Controle")
        self.assertEqual(cgu.situacao, Situacao.ANDAMENTO)
        # Da segunda coleta em diante, as mudanças ficam pendentes para o resumo.
        self.assertTrue(
            EventoDominio.objects.filter(
                tipo=EventoDominio.Tipo.CONCURSO_MUDOU_SITUACAO, concurso=cgu, processado_em__isnull=True
            ).exists()
        )

    def test_incluir_encerrados(self):
        cliente = cliente_cebraspe()
        cliente.respostas[URL_DETALHE.format(slug="PF_21")] = json.dumps({"eventoURL": "PF_21"}).encode()
        self.coletar(cliente, incluir_encerrados=True)
        pf = Concurso.objects.get(chave_externa="cebraspe:PF_21")
        self.assertEqual(pf.situacao, Situacao.ENCERRADO)
        self.assertIn("Policial", pf.areas.values_list("nome", flat=True))

    def test_pdf_fora_do_ar_nao_derruba_a_coleta(self):
        cliente = cliente_cebraspe()
        del cliente.respostas[URL_ARQUIVO.format(slug="CGU_26_AFFC", arquivo="A26FBD90.pdf")]
        execucao = self.coletar(cliente)
        self.assertEqual(execucao.status, Execucao.Status.OK)
        doc = Documento.objects.get(chave_externa="CGU_26_AFFC/A26FBD90.pdf")
        self.assertIn("erro_download", doc.metadados)
        self.assertEqual(doc.arquivo, "")

    def test_falha_na_api_registra_erro_e_evento(self):
        execucao = self.coletar(ClienteFalso({}))
        self.assertEqual(execucao.status, Execucao.Status.ERRO)
        self.assertTrue(EventoDominio.objects.filter(tipo=EventoDominio.Tipo.COLETA_FALHOU).exists())
        self.assertIn("404", execucao.fonte.ultimo_erro)
