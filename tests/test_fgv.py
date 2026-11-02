import unittest

from concursohub.adaptadores.fgv import URL_LISTA, FgvAdaptador, converter_detalhe, parse_lista, subpaginas
from concursohub.areas import areas_do_concurso
from concursohub.classificador import classificar_tipo
from concursohub.inferencia import inferir_esfera
from concursohub.modelos import Situacao, TipoDocumento

from .util import ClienteFalso, fixture

URL_TJPB = "https://conhecimento.fgv.br/concursos/tjpb26"


class FgvTests(unittest.TestCase):
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
        c = converter_detalhe(URL_TJPB, fixture("fgv_detalhe_tjpb.html").decode())
        self.assertEqual(c.chave_externa, "fgv:concursos/tjpb26")
        self.assertEqual(c.titulo, "Concurso Público para Tribunal de Justiça do Estado da Paraíba")
        self.assertEqual(c.situacao, Situacao.ANDAMENTO)
        self.assertEqual(c.ano, 2026)
        # Só os PDFs dos blocos de arquivos; inscrição e termos de uso ficam de fora.
        self.assertEqual([d.titulo for d in c.documentos], ["1ª Retificação", "Edital (retificado em 26/10/2026)"])
        self.assertTrue(c.documentos[1].url.startswith("https://conhecimento.fgv.br/sites/default/files/"))

    def test_area_esfera_e_tipos_pelo_titulo(self):
        # A FGV não estrutura cargos: área e esfera saem do título.
        c = converter_detalhe(URL_TJPB, fixture("fgv_detalhe_tjpb.html").decode())
        self.assertEqual(inferir_esfera(c.titulo), "estadual")
        self.assertEqual(areas_do_concurso(c.titulo), ["Tribunais"])
        self.assertEqual(
            [classificar_tipo(d.titulo) for d in c.documentos], [TipoDocumento.RETIFICACAO, TipoDocumento.EDITAL_ABERTURA]
        )

    def test_pagina_indice_vira_um_concurso_por_subpagina(self):
        # Caso real (29/10/2026): a página de Macaé não tem arquivos, só links para
        # um edital por órgão em /1, /2 e /3, cada um com o layout normal de detalhe.
        base = "https://conhecimento.fgv.br/concursos/prefeiturademacae24"
        indice = fixture("fgv_indice_macae.html").decode()
        self.assertEqual(converter_detalhe(base, indice).documentos, [])
        self.assertEqual([u for u, _ in subpaginas(base, indice)], [f"{base}/1", f"{base}/2", f"{base}/3"])

        lista = (
            '<div class="view-id-concursos_em_andamento"><div class="views-field-title">'
            '<a href="/concursos/prefeiturademacae24">Concurso Público para a Prefeitura de Macaé</a></div></div>'
        ).encode()
        cliente = ClienteFalso(
            {
                URL_LISTA.format(pagina=0): lista,
                URL_LISTA.format(pagina=1): b"<html></html>",
                base: fixture("fgv_indice_macae.html"),
                # /2 e /3 têm o mesmo layout; reaproveita a fixture de /1.
                **{f"{base}/{n}": fixture("fgv_detalhe_macae1.html") for n in (1, 2, 3)},
            }
        )
        concursos = list(FgvAdaptador(cliente).coletar())
        self.assertEqual(
            [c.chave_externa for c in concursos], [f"fgv:concursos/prefeiturademacae24/{n}" for n in (1, 2, 3)]
        )
        c = concursos[0]
        self.assertEqual(
            c.titulo,
            "Concurso Público para a Prefeitura de Macaé - Administração Pública Municipal Direta do Município de Macaé",
        )
        self.assertEqual(c.situacao, Situacao.ANDAMENTO)
        self.assertEqual(c.ano, 2024)
        self.assertGreater(len(c.documentos), 50)
