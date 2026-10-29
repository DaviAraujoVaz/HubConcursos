import io
import zipfile
from datetime import date

from django.test import override_settings

from ingestao.adaptadores.dou import URL_DOWNLOAD, DouAdaptador, InlabsSemCredenciais, documentos_de_concurso, parse_materias
from ingestao.coleta import executar
from ingestao.models import Documento, Execucao, TipoDocumento

from .util import ClienteFalso, TesteComDados

XML_EDITAL = """<xml><article id="1" name="edital-n-1-de-28-de-outubro-de-2026" idOficio="9" pubName="DO3"
 artType="Edital" pubDate="29/10/2026" artCategory="Ministério da Fazenda/Secretaria Especial da Receita Federal do Brasil"
 pdfPage="http://pesquisa.in.gov.br/imprensa/jsp/visualiza/index.jsp?data=29/10/2026&amp;jornal=530&amp;pagina=80"
 idMateria="555001"><body>
 <Identifica><![CDATA[EDITAL Nº 1, DE 28 DE OUTUBRO DE 2026]]></Identifica>
 <Ementa><![CDATA[]]></Ementa>
 <Texto><![CDATA[<p class="identifica">EDITAL Nº 1</p><p>O SECRETÁRIO torna pública a abertura de inscrições e as normas para a realização de concurso público destinado ao provimento de vagas no cargo de Auditor-Fiscal.</p>]]></Texto>
 </body></article></xml>"""

XML_OUTRO = """<xml><article id="2" name="portaria-n-7" pubName="DO2" artType="Portaria" pubDate="29/10/2026"
 artCategory="Ministério da Saúde" idMateria="555002"><body>
 <Identifica>PORTARIA Nº 7</Identifica><Texto><![CDATA[<p>Designa servidor para a função de chefe.</p>]]></Texto>
 </body></article></xml>"""

XML_HOMOLOGACAO = """<xml><article id="3" name="edital-n-20" pubName="DO3" artType="Edital" pubDate="29/10/2026"
 artCategory="Poder Judiciário/Tribunal Regional Federal da 1ª Região" idMateria="555003"><body>
 <Identifica>EDITAL Nº 20</Identifica>
 <Ementa>Homologação do resultado final do concurso público</Ementa>
 <Texto><![CDATA[<p>Torna pública a homologação do resultado final do concurso público.</p>]]></Texto>
 </body></article></xml>"""


def zip_com(*xmls: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as pacote:
        for i, xml in enumerate(xmls):
            pacote.writestr(f"materia_{i}.xml", xml.encode("utf-8"))
    return buffer.getvalue()


class DouParserTests(TesteComDados):
    def test_parse_materia(self):
        m = parse_materias(XML_EDITAL.encode())[0]
        self.assertEqual(m["id"], "555001")
        self.assertEqual(m["secao"], "DO3")
        self.assertEqual(m["identifica"], "EDITAL Nº 1, DE 28 DE OUTUBRO DE 2026")
        self.assertIn("realização de concurso público", m["texto"])
        self.assertNotIn("<p", m["texto"])

    def test_filtra_so_atos_de_concurso(self):
        docs = documentos_de_concurso(zip_com(XML_EDITAL, XML_OUTRO, XML_HOMOLOGACAO))
        self.assertEqual(len(docs), 2)
        por_chave = {d.chave_externa: d for d in docs}
        edital = por_chave["materia:555001"]
        self.assertEqual(edital.tipo, TipoDocumento.EDITAL_ABERTURA)
        self.assertIn("Receita Federal", edital.titulo)
        self.assertEqual(edital.publicado_em.date(), date(2026, 10, 29))
        self.assertEqual(por_chave["materia:555003"].tipo, TipoDocumento.HOMOLOGACAO)


@override_settings(INLABS_EMAIL="eu@exemplo.com", INLABS_SENHA="segredo-de-teste")
class DouColetaTests(TesteComDados):
    def test_coleta_um_dia(self):
        dia = "2026-10-29"
        cliente = ClienteFalso(
            {URL_DOWNLOAD.format(data=dia, secao="DO3"): zip_com(XML_EDITAL, XML_HOMOLOGACAO)},
            ao_postar=lambda c: c.sessao.cookies.__setitem__("inlabs_session_cookie", "abc"),
        )
        original = DouAdaptador.__init__
        DouAdaptador.__init__ = lambda self_, cliente_=None: original(self_, cliente)
        try:
            execucao = executar("dou", data_inicio=date(2026, 10, 29), data_fim=date(2026, 10, 29))
        finally:
            DouAdaptador.__init__ = original

        self.assertEqual(execucao.status, Execucao.Status.OK)
        self.assertEqual(execucao.documentos_novos, 2)
        doc = Documento.objects.get(chave_externa="materia:555001")
        self.assertIsNone(doc.concurso)
        self.assertTrue(doc.arquivo.endswith(".xml"))
        self.assertEqual(doc.metadados["secao"], "DO3")

    @override_settings(INLABS_EMAIL="", INLABS_SENHA="")
    def test_sem_credenciais_explica_o_que_fazer(self):
        with self.assertRaises(InlabsSemCredenciais):
            DouAdaptador(ClienteFalso({})).entrar()
