from datetime import timedelta

from django.utils import timezone

from catalogo.models import AreaAtuacao, Banca, Concurso, FiltroAlerta
from ingestao.avisos import processar
from ingestao.models import Documento, EventoDominio, Fonte, TipoDocumento
from ingestao.persistencia import emitir

from .util import TesteComDados


class AvisosTests(TesteComDados):
    def setUp(self):
        self.enviados = []
        self.fonte = Fonte.objects.get(slug="cebraspe")
        self.cebraspe = Banca.objects.get(slug="cebraspe")
        self.ti = AreaAtuacao.objects.get(nome="TI")
        self.concurso = Concurso.objects.create(chave_externa="t:1", titulo="CGU 26 AFFC", banca=self.cebraspe)
        self.concurso.areas.add(self.ti)

    def enviar(self, texto):
        self.enviados.append(texto)
        return True

    def documento(self, dias_atras=0, tipo=TipoDocumento.EDITAL_ABERTURA):
        doc = Documento.objects.create(
            fonte=self.fonte,
            concurso=self.concurso,
            chave_externa=f"d{dias_atras}{tipo}",
            titulo="Edital nº 1 - Abertura",
            tipo=tipo,
            publicado_em=timezone.now() - timedelta(days=dias_atras),
        )
        emitir(EventoDominio.Tipo.DOCUMENTO_PUBLICADO, concurso=self.concurso, documento=doc)
        return doc

    def test_sem_filtros_nao_avisa(self):
        self.documento()
        self.assertEqual(processar(enviar_fn=self.enviar), (1, 0))

    def test_filtro_por_banca_e_area(self):
        filtro = FiltroAlerta.objects.create(nome="TI na Cebraspe")
        filtro.bancas.add(self.cebraspe)
        filtro.areas.add(self.ti)
        self.documento()
        self.assertEqual(processar(enviar_fn=self.enviar), (1, 1))
        self.assertIn("CGU 26 AFFC", self.enviados[0])

    def test_filtro_que_nao_casa(self):
        filtro = FiltroAlerta.objects.create(nome="Saúde", esferas=["municipal"])
        filtro.areas.add(AreaAtuacao.objects.get(nome="Saúde"))
        self.documento()
        self.assertEqual(processar(enviar_fn=self.enviar), (1, 0))

    def test_tipo_de_documento(self):
        FiltroAlerta.objects.create(nome="Só retificações", tipos_documento=["retificacao"])
        self.documento(tipo=TipoDocumento.EDITAL_ABERTURA)
        self.documento(tipo=TipoDocumento.RETIFICACAO)
        self.assertEqual(processar(enviar_fn=self.enviar), (2, 1))

    def test_documento_antigo_nao_avisa(self):
        FiltroAlerta.objects.create(nome="Tudo")
        self.documento(dias_atras=60)
        self.assertEqual(processar(enviar_fn=self.enviar), (1, 0))

    def test_falha_de_coleta_sempre_avisa(self):
        emitir(EventoDominio.Tipo.COLETA_FALHOU, fonte="fgv", erro="HTTPError 503")
        self.assertEqual(processar(enviar_fn=self.enviar), (1, 1))
        self.assertIn("fgv", self.enviados[0])

    def test_nao_reprocessa(self):
        FiltroAlerta.objects.create(nome="Tudo")
        self.documento()
        processar(enviar_fn=self.enviar)
        self.assertEqual(processar(enviar_fn=self.enviar), (0, 0))
