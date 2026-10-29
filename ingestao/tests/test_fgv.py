from catalogo.models import Concurso, Situacao
from ingestao.adaptadores.fgv import URL_LISTA, FgvAdaptador, converter_detalhe, parse_lista
from ingestao.models import Documento, TipoDocumento
from ingestao.persistencia import persistir
from ingestao.models import Fonte

from .util import ClienteFalso, TesteComDados, fixture


class FgvTests(TesteComDados):
    def test_lista_so_em_andamento_por_padrao(self):
        html = fixture("fgv_lista_p0.html").decode()
        itens = parse_lista(html)
        self.assertEqual(
            [u for u, _, _ in itens],
            ["https://conhecimento.fgv.br/cpnu2", "https://conhecimento.fgv.br/concursos/tjpb26"],
        )
        com_realizados = parse_lista(html, incluir_realizados=True)
        self.assertEqual(len(com_realizados), 3)
        self.assertFalse(com_realizados[-1][2])

    def test_paginacao_para_quando_nao_ha_itens_novos(self):
        cliente = ClienteFalso(
            {
                URL_LISTA.format(pagina=0): fixture("fgv_lista_p0.html"),
                URL_LISTA.format(pagina=1): fixture("fgv_lista_p1.html"),
                URL_LISTA.format(pagina=2): fixture("fgv_lista_p1.html"),  # repetida = fim
            }
        )
        itens = FgvAdaptador(cliente).listar()
        self.assertEqual(len(itens), 3)
        self.assertNotIn(URL_LISTA.format(pagina=3), cliente.pedidos)

    def test_detalhe(self):
        url = "https://conhecimento.fgv.br/concursos/tjpb26"
        c = converter_detalhe(url, fixture("fgv_detalhe_tjpb.html").decode())
        self.assertEqual(c.chave_externa, "fgv:concursos/tjpb26")
        self.assertEqual(c.titulo, "Concurso Público para Tribunal de Justiça do Estado da Paraíba")
        self.assertEqual(c.situacao, Situacao.ANDAMENTO)
        self.assertEqual(c.ano, 2026)
        # Só os PDFs dos blocos de arquivos; inscrição e termos de uso ficam de fora.
        self.assertEqual(
            [d.titulo for d in c.documentos], ["1ª Retificação", "Edital (retificado em 26/10/2026)"]
        )
        self.assertTrue(c.documentos[1].url.startswith("https://conhecimento.fgv.br/sites/default/files/"))

    def test_persistencia_com_areas_e_esfera_pelo_titulo(self):
        url = "https://conhecimento.fgv.br/concursos/tjpb26"
        c = converter_detalhe(url, fixture("fgv_detalhe_tjpb.html").decode())
        from ingestao.adaptadores.base import ResultadoColeta

        fonte = Fonte.objects.get(slug="fgv")
        persistir(fonte, FgvAdaptador(ClienteFalso({})), ResultadoColeta(concursos=[c]), baixar_arquivos=False)
        concurso = Concurso.objects.get(chave_externa="fgv:concursos/tjpb26")
        self.assertEqual(concurso.banca.slug, "fgv")
        self.assertEqual(concurso.esfera, "estadual")
        self.assertEqual(list(concurso.areas.values_list("nome", flat=True)), ["Tribunais"])
        tipos = set(Documento.objects.filter(concurso=concurso).values_list("tipo", flat=True))
        self.assertEqual(tipos, {TipoDocumento.RETIFICACAO, TipoDocumento.EDITAL_ABERTURA})
