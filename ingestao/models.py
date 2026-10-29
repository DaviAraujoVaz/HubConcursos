"""Proveniência e operação da coleta.

- Fonte: cada site/diário coletado, com a saúde da última execução.
- Documento: todo arquivo oficial encontrado (edital, retificação, ato do DOU…).
  É daqui que sai cada dado do catálogo.
- Execucao: histórico de cada rodada de coleta, para saber quando algo quebrou.
- EventoDominio: "caixa de saída" de acontecimentos (concurso novo, documento novo,
  coleta falhou). Avisos e features futuras leem daqui sem mexer na coleta.
"""
from django.db import models


class Fonte(models.Model):
    slug = models.SlugField(unique=True)
    nome = models.CharField(max_length=120)
    ativa = models.BooleanField(default=True)
    ultima_execucao = models.DateTimeField(null=True, blank=True)
    ultimo_sucesso = models.DateTimeField(null=True, blank=True)
    ultimo_erro = models.TextField(blank=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class TipoDocumento(models.TextChoices):
    AUTORIZACAO = "autorizacao", "Autorização"
    EDITAL_ABERTURA = "edital_abertura", "Edital de abertura"
    RETIFICACAO = "retificacao", "Retificação"
    COMUNICADO = "comunicado", "Comunicado"
    INSCRITOS = "inscritos", "Inscritos / demanda"
    GABARITO = "gabarito", "Gabarito"
    RESULTADO = "resultado", "Resultado"
    CONVOCACAO = "convocacao", "Convocação"
    HOMOLOGACAO = "homologacao", "Homologação"
    PRORROGACAO = "prorrogacao", "Prorrogação de validade"
    CONTRATACAO_BANCA = "contratacao_banca", "Contratação de banca"
    OUTRO = "outro", "Outro"


class Documento(models.Model):
    fonte = models.ForeignKey(Fonte, on_delete=models.PROTECT, related_name="documentos")
    concurso = models.ForeignKey(
        "catalogo.Concurso", on_delete=models.SET_NULL, null=True, blank=True, related_name="documentos"
    )
    chave_externa = models.CharField(max_length=300, help_text="Identificador estável na fonte (URL, id da matéria…).")
    tipo = models.CharField(max_length=20, choices=TipoDocumento.choices, default=TipoDocumento.OUTRO)
    titulo = models.CharField(max_length=600)
    url = models.URLField(max_length=800, blank=True)
    publicado_em = models.DateTimeField(null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    arquivo = models.CharField(max_length=400, blank=True, help_text="Caminho do bruto em DADOS_DIR.")
    texto = models.TextField(blank=True)
    metadados = models.JSONField(default=dict, blank=True)
    precisa_revisao = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("fonte", "chave_externa")]
        ordering = ["-publicado_em", "-criado_em"]

    def __str__(self):
        return self.titulo[:120]


class Execucao(models.Model):
    class Status(models.TextChoices):
        RODANDO = "rodando", "Rodando"
        OK = "ok", "OK"
        ERRO = "erro", "Erro"

    fonte = models.ForeignKey(Fonte, on_delete=models.CASCADE, related_name="execucoes")
    inicio = models.DateTimeField(auto_now_add=True)
    fim = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RODANDO)
    concursos_vistos = models.PositiveIntegerField(default=0)
    concursos_novos = models.PositiveIntegerField(default=0)
    documentos_novos = models.PositiveIntegerField(default=0)
    erro = models.TextField(blank=True)

    class Meta:
        verbose_name = "execução"
        verbose_name_plural = "execuções"
        ordering = ["-inicio"]

    def __str__(self):
        return f"{self.fonte} {self.inicio:%d/%m %H:%M} — {self.get_status_display()}"


class EventoDominio(models.Model):
    class Tipo(models.TextChoices):
        CONCURSO_DESCOBERTO = "concurso_descoberto", "Concurso descoberto"
        CONCURSO_MUDOU_SITUACAO = "concurso_mudou_situacao", "Situação do concurso mudou"
        DOCUMENTO_PUBLICADO = "documento_publicado", "Documento publicado"
        COLETA_FALHOU = "coleta_falhou", "Coleta falhou"

    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    payload = models.JSONField(default=dict)
    concurso = models.ForeignKey("catalogo.Concurso", on_delete=models.CASCADE, null=True, blank=True)
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    processado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "evento de domínio"
        verbose_name_plural = "eventos de domínio"
        ordering = ["criado_em"]

    def __str__(self):
        return f"{self.get_tipo_display()} ({self.criado_em:%d/%m %H:%M})"
