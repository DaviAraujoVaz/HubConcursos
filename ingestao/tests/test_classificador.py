from django.test import SimpleTestCase

from ingestao.classificador import classificar_tipo, eh_ato_de_concurso
from ingestao.models import TipoDocumento as T


class ClassificadorTipoTests(SimpleTestCase):
    def test_titulos_reais(self):
        casos = {
            "Edital nº 1 - Abertura": T.EDITAL_ABERTURA,
            "Edital nº 1 - Abertura - Atualizado conforme retificações": T.EDITAL_ABERTURA,
            "Edital nº 2 – Retificação do subitem 6.2.4 e do Anexo I – Cronograma Previsto do Edital nº 1": T.RETIFICACAO,
            "1ª Retificação": T.RETIFICACAO,
            "Comunicado – Pagamento da taxa de inscrição via Pix ficará indisponível": T.COMUNICADO,
            "Gabaritos oficiais preliminares das provas objetivas": T.GABARITO,
            "Demanda de candidatos por vaga": T.INSCRITOS,
            "Edital nº 15 – Resultado final na avaliação biopsicossocial e homologação do resultado final": T.HOMOLOGACAO,
            "Edital nº 9 – Resultado final nas provas objetivas": T.RESULTADO,
            "PORTARIA Nº 123 - Autoriza a realização de concurso público para o cargo de Analista": T.AUTORIZACAO,
            "EXTRATO DE DISPENSA DE LICITAÇÃO - organização e realização de concurso público": T.CONTRATACAO_BANCA,
            "Prorroga o prazo de validade do concurso público": T.PRORROGACAO,
            "Termo aditivo ao contrato de limpeza": T.OUTRO,
        }
        for titulo, esperado in casos.items():
            with self.subTest(titulo=titulo):
                self.assertEqual(classificar_tipo(titulo), esperado)

    def test_reconhece_ato_de_concurso(self):
        self.assertTrue(eh_ato_de_concurso("EDITAL Nº 1", "Torna pública a abertura de Concurso Público"))
        self.assertTrue(eh_ato_de_concurso("", "", "processo seletivo simplificado para professor"))
        self.assertFalse(eh_ato_de_concurso("PORTARIA Nº 7", "Designa servidor para função"))
