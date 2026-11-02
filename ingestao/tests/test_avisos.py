from datetime import datetime, time, timedelta
from unittest import mock

from django.core import mail
from django.test import override_settings
from django.utils import timezone

from catalogo.models import AreaAtuacao, Banca, Concurso, FiltroAlerta, Situacao
from ingestao.avisos import processar
from ingestao.coleta import silenciar_eventos
from ingestao.models import Documento, EventoDominio, Fonte, ResumoAviso, TipoDocumento
from ingestao.persistencia import emitir

from .util import TesteComDados


def hoje_as(hora: int) -> datetime:
    return timezone.make_aware(datetime.combine(timezone.localdate(), time(hora)))


@override_settings(AVISOS_EMAIL_PARA="eu@exemplo.com", AVISOS_HORA=7, AVISOS_MAX_CONCURSOS=40)
class AvisosTests(TesteComDados):
    def setUp(self):
        self.fonte = Fonte.objects.get(slug="cebraspe")
        self.cebraspe = Banca.objects.get(slug="cebraspe")
        self.ti = AreaAtuacao.objects.get(nome="TI")
        self.concurso = self.novo_concurso("CGU 26 AFFC")

    def novo_concurso(self, titulo, **campos):
        concurso = Concurso.objects.create(chave_externa=f"t:{titulo}", titulo=titulo, banca=self.cebraspe, **campos)
        concurso.areas.add(self.ti)
        return concurso

    def documento(self, dias_atras=0, tipo=TipoDocumento.EDITAL_ABERTURA, concurso=None, titulo="Edital nº 1 - Abertura"):
        concurso = concurso or self.concurso
        doc = Documento.objects.create(
            fonte=self.fonte,
            concurso=concurso,
            chave_externa=f"{concurso.pk}-{titulo}-{dias_atras}-{tipo}",
            titulo=titulo,
            tipo=tipo,
            url="https://cdn.cebraspe.org.br/edital.pdf",
            publicado_em=timezone.now() - timedelta(days=dias_atras),
        )
        emitir(EventoDominio.Tipo.DOCUMENTO_PUBLICADO, concurso=concurso, documento=doc, fonte="cebraspe")
        return doc

    def filtro_ti(self):
        filtro = FiltroAlerta.objects.create(nome="TI na Cebraspe")
        filtro.bancas.add(self.cebraspe)
        filtro.areas.add(self.ti)
        return filtro

    def pendentes(self):
        return EventoDominio.objects.filter(processado_em__isnull=True).count()

    # --- O que entra no resumo -------------------------------------------------

    def test_sem_filtros_nao_avisa(self):
        self.documento()
        resultado = processar(forcar=True)
        self.assertEqual((resultado.processados, resultado.resumo), (1, None))
        self.assertEqual(len(mail.outbox), 0)

    def test_filtro_por_banca_e_area(self):
        self.filtro_ti()
        doc = self.documento()
        resultado = processar(forcar=True)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["eu@exemplo.com"])
        self.assertEqual(email.subject, "ConcursoHub: 1 concurso com novidades")
        self.assertIn("CGU 26 AFFC", email.body)
        self.assertIn(doc.url, email.body)
        html = email.alternatives[0][0]
        self.assertIn(f'href="{doc.url}"', html)
        self.assertEqual(list(resultado.resumo.eventos.values_list("documento", flat=True)), [doc.pk])

    def test_filtro_que_nao_casa(self):
        filtro = FiltroAlerta.objects.create(nome="Saúde", esferas=["municipal"])
        filtro.areas.add(AreaAtuacao.objects.get(nome="Saúde"))
        self.documento()
        self.assertIsNone(processar(forcar=True).resumo)
        self.assertEqual(self.pendentes(), 0)

    def test_tipo_de_documento(self):
        FiltroAlerta.objects.create(nome="Só retificações", tipos_documento=["retificacao"])
        self.documento(tipo=TipoDocumento.EDITAL_ABERTURA, titulo="Edital de abertura")
        self.documento(tipo=TipoDocumento.RETIFICACAO, titulo="Edital de retificação")
        processar(forcar=True)
        self.assertIn("Edital de retificação", mail.outbox[0].body)
        self.assertNotIn("Edital de abertura", mail.outbox[0].body)

    def test_documento_antigo_nao_avisa(self):
        FiltroAlerta.objects.create(nome="Tudo")
        self.documento(dias_atras=60)
        self.assertIsNone(processar(forcar=True).resumo)

    def test_concurso_ja_encerrado_nao_e_novidade(self):
        # Coleta de histórico (--encerrados) não pode virar enxurrada.
        FiltroAlerta.objects.create(nome="Tudo")
        antigo = self.novo_concurso("PF 21", situacao=Situacao.ENCERRADO)
        emitir(EventoDominio.Tipo.CONCURSO_DESCOBERTO, concurso=antigo, fonte="cebraspe")
        self.assertIsNone(processar(forcar=True).resumo)

    def test_falha_de_coleta_sempre_avisa(self):
        emitir(EventoDominio.Tipo.COLETA_FALHOU, fonte="fgv", erro="HTTPError 503")
        processar(forcar=True)
        self.assertIn("fgv: HTTPError 503", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].subject, "ConcursoHub: 1 falha de coleta")

    def test_agrupa_por_concurso(self):
        self.filtro_ti()
        emitir(EventoDominio.Tipo.CONCURSO_DESCOBERTO, concurso=self.concurso, fonte="cebraspe")
        emitir(EventoDominio.Tipo.CONCURSO_MUDOU_SITUACAO, concurso=self.concurso, de="previsto", para="aberto")
        self.documento(titulo="Edital nº 1 - Abertura")
        self.documento(titulo="Edital nº 2 - Retificação", tipo=TipoDocumento.RETIFICACAO)
        resultado = processar(forcar=True)
        corpo = mail.outbox[0].body
        self.assertEqual(corpo.count("CGU 26 AFFC"), 1)
        self.assertIn("[novo; situação: Previsto → Inscrições abertas]", corpo)
        self.assertIn("Edital nº 2 - Retificação", corpo)
        self.assertEqual(resultado.resumo.eventos.count(), 4)

    @override_settings(AVISOS_MAX_CONCURSOS=2)
    def test_resumo_tem_limite_de_concursos(self):
        self.filtro_ti()
        for numero in range(5):
            concurso = self.novo_concurso(f"TRT {numero} 26")
            self.documento(concurso=concurso)
        resultado = processar(forcar=True)
        corpo = mail.outbox[0].body
        self.assertIn("E mais 3 concursos com novidades", corpo)
        self.assertEqual(mail.outbox[0].subject, "ConcursoHub: 5 concursos com novidades")
        # Os omitidos também contam como avisados: não voltam amanhã.
        self.assertEqual(resultado.resumo.eventos.count(), 5)
        self.assertEqual(self.pendentes(), 0)

    def test_prazos_de_inscricao(self):
        self.filtro_ti()
        self.concurso.inscricoes_fim = timezone.now() + timedelta(days=3)
        self.concurso.url_oficial = "https://www.cebraspe.org.br/concursos/CGU_26_AFFC"
        self.concurso.save()
        self.novo_concurso("TJ CE 25", inscricoes_fim=timezone.now() + timedelta(days=30))
        processar(forcar=True)
        corpo = mail.outbox[0].body
        self.assertIn("INSCRIÇÕES TERMINANDO", corpo)
        self.assertIn("(em 3 dias): CGU 26 AFFC", corpo)
        self.assertNotIn("TJ CE 25", corpo)

    # --- Quando e como envia ---------------------------------------------------

    def test_um_resumo_por_dia_a_partir_do_horario(self):
        self.filtro_ti()
        self.documento()
        cedo = processar(agora=hoje_as(6))
        self.assertIsNone(cedo.resumo)
        self.assertEqual(self.pendentes(), 1)  # espera o horário, não descarta

        self.assertTrue(processar(agora=hoje_as(8)).resumo.ok)
        self.documento(titulo="Edital nº 2")
        self.assertEqual(processar(agora=hoje_as(11)).motivo, "o resumo de hoje já foi enviado")
        self.assertEqual((len(mail.outbox), self.pendentes()), (1, 1))

        amanha = hoje_as(8) + timedelta(days=1)
        self.assertTrue(processar(agora=amanha).resumo.ok)
        self.assertEqual(len(mail.outbox), 2)

    def test_falha_no_envio_mantem_eventos_pendentes(self):
        self.filtro_ti()
        self.documento()
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("SMTP fora do ar")):
            resultado = processar(forcar=True)
        self.assertFalse(resultado.resumo.ok)
        self.assertIn("SMTP fora do ar", resultado.resumo.erro)
        self.assertEqual(self.pendentes(), 1)
        # Falha não conta como "resumo de hoje": a próxima rotina tenta de novo.
        self.assertTrue(processar(agora=hoje_as(23)).resumo.ok)
        self.assertEqual(self.pendentes(), 0)

    @override_settings(AVISOS_EMAIL_PARA="")
    def test_sem_email_configurado_vai_para_o_log(self):
        self.filtro_ti()
        self.documento()
        with self.assertLogs("ingestao.avisos", "INFO") as logs:
            resultado = processar(forcar=True)
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(resultado.resumo.ok)
        self.assertIn("CGU 26 AFFC", logs.output[0])

    def test_previa_nao_envia_nem_marca(self):
        self.filtro_ti()
        self.documento()
        resultado = processar(previa=True)
        self.assertIn("CGU 26 AFFC", resultado.motivo)
        self.assertEqual((len(mail.outbox), self.pendentes(), ResumoAviso.objects.count()), (0, 1, 0))

    def test_nao_reprocessa(self):
        self.filtro_ti()
        self.documento()
        processar(forcar=True)
        self.assertEqual(processar(forcar=True).processados, 0)

    def test_silenciar_eventos_da_primeira_coleta(self):
        inicio = timezone.now()
        self.documento()
        emitir(EventoDominio.Tipo.COLETA_FALHOU, fonte="cebraspe", erro="timeout")
        emitir(EventoDominio.Tipo.CONCURSO_DESCOBERTO, concurso=self.concurso, fonte="fgv")
        self.assertEqual(silenciar_eventos("cebraspe", desde=inicio), 1)
        # A falha e o evento de outra fonte continuam pendentes.
        self.assertEqual(self.pendentes(), 2)
