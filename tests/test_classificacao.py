"""Casos reais de classificação. Antes de ajustar uma regra, adicione o caso aqui."""
import unittest

from concursohub.areas import areas_do_concurso
from concursohub.classificador import classificar_tipo
from concursohub.inferencia import inferir_esfera
from concursohub.modelos import Esfera
from concursohub.modelos import TipoDocumento as T


class TipoDocumentoTests(unittest.TestCase):
    def test_titulos_reais(self):
        casos = {
            "Edital nº 1 - Abertura": T.EDITAL_ABERTURA,
            "Edital nº 1 - Abertura - Atualizado conforme retificações": T.EDITAL_ABERTURA,
            "Edital (retificado em 26/10/2026)": T.EDITAL_ABERTURA,
            "Edital": T.EDITAL_ABERTURA,  # FGV (DPE-RJ 26, INB 26)
            "EDITAL Nº 112/2025 - DRH/SEAP - PcD": T.OUTRO,
            "Edital nº 2 – Retificação do subitem 6.2.4 e do Anexo I – Cronograma Previsto do Edital nº 1": T.RETIFICACAO,
            "1ª Retificação": T.RETIFICACAO,
            "Comunicado – Pagamento da taxa de inscrição via Pix ficará indisponível": T.COMUNICADO,
            "Gabaritos oficiais preliminares das provas objetivas": T.GABARITO,
            "Demanda de candidatos por vaga": T.INSCRITOS,
            "Edital nº 15 – Resultado final na avaliação biopsicossocial e homologação do resultado final": T.HOMOLOGACAO,
            "Edital nº 9 – Resultado final nas provas objetivas": T.RESULTADO,
            "Prorroga o prazo de validade do concurso público": T.PRORROGACAO,
            "Termo aditivo ao contrato de limpeza": T.OUTRO,
        }
        for titulo, esperado in casos.items():
            with self.subTest(titulo=titulo):
                self.assertEqual(classificar_tipo(titulo), esperado)


class EsferaTests(unittest.TestCase):
    def test_inferencia_pelo_titulo(self):
        casos = {
            "TJ CE 25 NOTÁRIOS": Esfera.ESTADUAL,
            "CÂMARA DOS DEPUTADOS 26 ANALISTA": Esfera.FEDERAL,
            "CGU 26 AFFC": Esfera.FEDERAL,
            "PC PE 26": Esfera.ESTADUAL,
            "Concurso Público para a Prefeitura de Macaé": Esfera.MUNICIPAL,
            "SEDF 26 PROFESSOR": Esfera.DISTRITAL,
            "Concurso Público para Tribunal de Justiça do Estado da Paraíba": Esfera.ESTADUAL,
            "Concurso Público Nacional Unificado 2": Esfera.FEDERAL,
            # Padrão Cebraspe "SIGLA UF AA" (casos reais da primeira coleta)
            "AGEPAR PR 26": Esfera.ESTADUAL,
            "AGSUS 26 ACOLHEDORA": Esfera.FEDERAL,
            "PF 25": Esfera.FEDERAL,
            "PREF ANDRADINA 25 PROCURADOR": Esfera.MUNICIPAL,
            "PREF. DE BOA VISTA 25 SAUDE": Esfera.MUNICIPAL,
            "PREF PORTO ALEGRE RS 26": Esfera.MUNICIPAL,
            "SEFAZ/RJ 25 ANALISTA": Esfera.ESTADUAL,
            "Concurso para provimento do cargo efetivo de Conselheiro Substituto (Auditor) do TCE/AC": Esfera.ESTADUAL,
            "POLÍCIA MILITAR DE SANTA CATARINA": Esfera.ESTADUAL,
            "Perícia Oficial de Natureza Criminal do Maranhão": Esfera.ESTADUAL,
            "ALAGOAS PREVIDÊNCIA": Esfera.ESTADUAL,
            "Concurso Público para o Tribunal de Justiça do Pará": Esfera.ESTADUAL,
            "Concurso Público para a Agência X": "",  # "para" não é o estado do Pará
            "ANTAQ 25 CF": Esfera.FEDERAL,
            "FUNPRESP 26 JUD": Esfera.FEDERAL,
            "DREI 26 EXAME APTIDÃO": Esfera.FEDERAL,
            # FGV
            "Concurso Público para a Amazônia Azul Tecnologias de Defesa S.A. - AMAZUL": Esfera.FEDERAL,
            "Concurso Público para a Companhia de Pesquisa de Recursos Minerais - CPRM": Esfera.FEDERAL,
            "Concurso Público para a NAV Brasil Serviços de Navegação Aérea S.A.": Esfera.FEDERAL,
            "Concurso Público para o Cargo Especialista em Políticas Públicas e Gestão Governamental - SEAD/SE": Esfera.ESTADUAL,
        }
        for titulo, esperada in casos.items():
            with self.subTest(titulo=titulo):
                self.assertEqual(inferir_esfera(titulo), esperada)


class AreaTests(unittest.TestCase):
    def test_palavra_inteira_e_prefixo(self):
        # "tre" (TRE) não pode casar com "entre"; "professor*" casa "professora".
        self.assertEqual(areas_do_concurso("Seleção entre servidores"), [])
        self.assertEqual(areas_do_concurso("TRE SP 26"), ["Tribunais"])
        self.assertEqual(areas_do_concurso("X 26", ["Professora de Matemática"]), ["Educação"])

    def test_titulo_e_cargos_se_somam(self):
        # Um analista de TI de tribunal entra em Tribunais e em TI.
        self.assertEqual(areas_do_concurso("TJ PB 26", ["Analista Judiciário - Área de TI"]), ["TI", "Tribunais"])
        # Termo de órgão não vale no nome do cargo ("Técnico em PC" não é Polícia Civil).
        self.assertEqual(areas_do_concurso("X 26", ["Técnico de PC"]), [])

    def test_casos_reais_da_primeira_coleta(self):
        casos = {
            "Secretaria de Estado da Educação de Alagoas": ["Educação"],
            "Secretaria de Estado da Saúde de Alagoas": ["Saúde"],
            "Secretaria de Estado da Fazenda de Alagoas": ["Fiscal"],
            "AGÊNCIA REGULADORA DE SERVIÇOS PÚBLICOS DO ESTADO DE ALAGOAS": ["Regulação"],
            "Concurso Público para a Prefeitura Municipal de Vitória - Guarda Municipal": ["Policial"],
            "Concurso Público para a Prefeitura do Rio de Janeiro - Gestor de Segurança Municipal": ["Policial"],
            "Concurso Público para a Secretaria de Administração Penitenciária e Ressocialização do Estado da Bahia - SEAP-BA": ["Policial"],
            "Concurso Público para a Contadoria e Auditoria-Geral do Estado do Rio Grande do Sul (CAGE RS)": ["Controle"],
        }
        for titulo, esperadas in casos.items():
            with self.subTest(titulo=titulo):
                self.assertEqual(areas_do_concurso(titulo), esperadas)
