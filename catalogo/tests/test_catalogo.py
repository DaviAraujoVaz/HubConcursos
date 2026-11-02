from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from catalogo.classificacao import areas_para, classificar_concurso
from catalogo.inferencia import inferir_esfera
from catalogo.models import AreaAtuacao, AtributoDefinicao, Cargo, Concurso, Esfera, Orgao, RegraArea, Situacao


class EsferaTests(TestCase):
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

    def test_orgao_vinculado_prevalece(self):
        orgao = Orgao.objects.create(nome="Prefeitura de Brasília?", esfera=Esfera.DISTRITAL)
        c = Concurso.objects.create(chave_externa="x", titulo="Concurso Federal qualquer", orgao=orgao)
        self.assertEqual(c.esfera, Esfera.DISTRITAL)


class AreaTests(TestCase):
    def nomes(self, ids):
        return sorted(AreaAtuacao.objects.filter(id__in=ids).values_list("nome", flat=True))

    def test_palavra_inteira_e_prefixo(self):
        # "tre" (TRE) não pode casar com "entre"; "professor*" casa "professora".
        self.assertEqual(self.nomes(areas_para("", "Seleção entre servidores", alvos=("orgao",))), [])
        self.assertEqual(self.nomes(areas_para("", "TRE SP 26", alvos=("orgao",))), ["Tribunais"])
        self.assertEqual(self.nomes(areas_para("Professora de Matemática", "", alvos=("cargo",))), ["Educação"])

    def test_secretarias_de_estado_e_agencias_reguladoras(self):
        # Títulos reais da primeira coleta da Cebraspe (01/11/2026).
        casos = {
            "Secretaria de Estado da Educação de Alagoas": ["Educação"],
            "Secretaria de Estado da Saúde de Alagoas": ["Saúde"],
            "Secretaria de Estado da Fazenda de Alagoas": ["Fiscal"],
            "AGÊNCIA REGULADORA DE SERVIÇOS PÚBLICOS DO ESTADO DE ALAGOAS": ["Regulação"],
            # FGV (sem cargos estruturados; a área sai do título)
            "Concurso Público para a Prefeitura Municipal de Vitória - Guarda Municipal": ["Policial"],
            "Concurso Público para a Prefeitura do Rio de Janeiro - Gestor de Segurança Municipal": ["Policial"],
            "Concurso Público para a Secretaria de Administração Penitenciária e Ressocialização do Estado da Bahia - SEAP-BA": ["Policial"],
            "Concurso Público para a Contadoria e Auditoria-Geral do Estado do Rio Grande do Sul (CAGE RS)": ["Controle"],
        }
        for titulo, esperadas in casos.items():
            with self.subTest(titulo=titulo):
                self.assertEqual(self.nomes(areas_para("", titulo, alvos=("orgao",))), esperadas)

    def test_concurso_recebe_uniao_dos_cargos_e_titulo(self):
        c = Concurso.objects.create(chave_externa="c", titulo="TJ PB 26")
        Cargo.objects.create(concurso=c, nome="Analista Judiciário - Área de TI")
        classificar_concurso(c)
        self.assertEqual(sorted(c.areas.values_list("nome", flat=True)), ["TI", "Tribunais"])

    def test_ajuste_manual_e_respeitado(self):
        c = Concurso.objects.create(chave_externa="c", titulo="TJ PB 26", areas_manuais=True)
        classificar_concurso(c)
        self.assertEqual(c.areas.count(), 0)

    def test_regra_nova_vale_na_reclassificacao(self):
        c = Concurso.objects.create(chave_externa="c", titulo="ABDI 26")
        classificar_concurso(c)
        self.assertEqual(c.areas.count(), 0)
        RegraArea.objects.create(termo="abdi", alvo="orgao", area=AreaAtuacao.objects.get(nome="Administrativa"))
        classificar_concurso(c)
        self.assertEqual(list(c.areas.values_list("nome", flat=True)), ["Administrativa"])


class AdminECalendarioTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("eu", "eu@exemplo.com", "senha-de-teste-123")
        self.client.force_login(self.user)
        self.concurso = Concurso.objects.create(
            chave_externa="c",
            titulo="CGU 26 AFFC",
            situacao=Situacao.ABERTO,
            inscricoes_fim=timezone.now() + timedelta(days=5),
            atributos={"exige_cnh": True},
        )
        classificar_concurso(self.concurso)

    def test_lista_com_filtros_de_area_esfera_e_atributo(self):
        AtributoDefinicao.objects.create(chave="exige_cnh", rotulo="Exige CNH")
        resposta = self.client.get("/admin/catalogo/concurso/")
        self.assertEqual(resposta.status_code, 200)
        conteudo = resposta.content.decode()
        for trecho in ("área de atuação", "Exige CNH", "Controle"):
            self.assertIn(trecho, conteudo)
        filtrado = self.client.get("/admin/catalogo/concurso/?area=controle&esfera__exact=federal&attr_exige_cnh=1")
        self.assertContains(filtrado, "CGU 26 AFFC")
        vazio = self.client.get("/admin/catalogo/concurso/?area=saude")
        self.assertNotContains(vazio, "CGU 26 AFFC")

    def test_paginas_do_admin_abrem(self):
        for url in (
            f"/admin/catalogo/concurso/{self.concurso.pk}/change/",
            "/admin/catalogo/cargo/",
            "/admin/catalogo/areaatuacao/",
            "/admin/ingestao/documento/?vinculado=nao",
            "/admin/ingestao/fonte/",
            "/admin/ingestao/execucao/",
            "/admin/catalogo/filtroalerta/add/",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_calendario_ics(self):
        resposta = self.client.get("/calendario.ics")
        self.assertEqual(resposta["Content-Type"], "text/calendar; charset=utf-8")
        self.assertContains(resposta, "BEGIN:VCALENDAR")
        self.assertContains(resposta, "Último dia de inscrição: CGU 26 AFFC")
