"""Modelo de dados do catálogo de concursos.

A unidade que importa para o candidato é a vaga (cargo × localidade × modalidade).
O concurso agrupa cargos, documentos e eventos. Campos estáveis são colunas;
o resto vai para `atributos` (JSON), descrito pela tabela AtributoDefinicao.
"""
from django.db import models
from django.utils.text import slugify


class Esfera(models.TextChoices):
    FEDERAL = "federal", "Federal"
    ESTADUAL = "estadual", "Estadual"
    DISTRITAL = "distrital", "Distrital"
    MUNICIPAL = "municipal", "Municipal"


class Poder(models.TextChoices):
    EXECUTIVO = "executivo", "Executivo"
    LEGISLATIVO = "legislativo", "Legislativo"
    JUDICIARIO = "judiciario", "Judiciário"
    MINISTERIO_PUBLICO = "mp", "Ministério Público"
    DEFENSORIA = "defensoria", "Defensoria"
    TRIBUNAL_CONTAS = "tc", "Tribunal de Contas"
    ESTATAL = "estatal", "Empresa estatal"


class Orgao(models.Model):
    nome = models.CharField(max_length=300)
    sigla = models.CharField(max_length=40, blank=True)
    cnpj = models.CharField("CNPJ", max_length=14, blank=True, null=True, unique=True)
    esfera = models.CharField(max_length=12, choices=Esfera.choices, blank=True)
    poder = models.CharField(max_length=12, choices=Poder.choices, blank=True)
    uf = models.CharField("UF", max_length=2, blank=True)
    municipio_ibge = models.CharField("Município (código IBGE)", max_length=7, blank=True)
    apelidos = models.JSONField(default=list, blank=True, help_text="Outros nomes, para deduplicar.")

    class Meta:
        verbose_name = "órgão"
        verbose_name_plural = "órgãos"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.sigla} — {self.nome}" if self.sigla else self.nome


class Banca(models.Model):
    nome = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(unique=True)
    site = models.URLField(blank=True)
    apelidos = models.JSONField(default=list, blank=True, help_text='Ex.: ["Cespe", "Cespe/UnB"]')

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class AreaAtuacao(models.Model):
    """Taxonomia de áreas de atuação (Tribunais, Fiscal, TI…), editável no admin."""

    nome = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)
    descricao = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "área de atuação"
        verbose_name_plural = "áreas de atuação"
        ordering = ["nome"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class RegraArea(models.Model):
    """Dicionário que classifica cargos em áreas. Cada correção sua vira uma regra."""

    class Alvo(models.TextChoices):
        CARGO = "cargo", "Nome do cargo"
        ORGAO = "orgao", "Nome do órgão ou título do concurso"

    termo = models.CharField(
        max_length=120,
        help_text="Trecho procurado sem diferenciar maiúsculas e acentos. Ex.: 'auditor-fiscal'.",
    )
    alvo = models.CharField(max_length=10, choices=Alvo.choices, default=Alvo.CARGO)
    area = models.ForeignKey(AreaAtuacao, on_delete=models.CASCADE, related_name="regras")
    ativa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "regra de área"
        verbose_name_plural = "regras de área"
        unique_together = [("termo", "alvo", "area")]
        ordering = ["area__nome", "termo"]

    def __str__(self):
        return f"{self.get_alvo_display()}: '{self.termo}' → {self.area}"


class Situacao(models.TextChoices):
    PREVISTO = "previsto", "Previsto"
    AUTORIZADO = "autorizado", "Autorizado"
    ABERTO = "aberto", "Inscrições abertas"
    ANDAMENTO = "andamento", "Em andamento"
    HOMOLOGADO = "homologado", "Homologado"
    ENCERRADO = "encerrado", "Encerrado"


class Maturidade(models.TextChoices):
    """Sinal mais forte encontrado de que o concurso vai acontecer."""

    RUMOR = "1_rumor", "Notícia/rumor"
    SOLICITADO = "2_solicitado", "Pedido de autorização"
    AUTORIZADO = "3_autorizado", "Autorizado"
    BANCA = "4_banca", "Banca contratada"
    EDITAL = "5_edital", "Edital publicado"


class Concurso(models.Model):
    chave_externa = models.CharField(
        max_length=200, unique=True, help_text="Identificador na fonte, ex.: 'cebraspe:CGU_26_AFFC'."
    )
    titulo = models.CharField(max_length=400)
    orgao = models.ForeignKey(Orgao, on_delete=models.SET_NULL, null=True, blank=True, related_name="concursos")
    banca = models.ForeignKey(Banca, on_delete=models.SET_NULL, null=True, blank=True, related_name="concursos")
    esfera = models.CharField(
        max_length=12,
        choices=Esfera.choices,
        blank=True,
        help_text="Vem do órgão quando ele está vinculado; senão, é inferida do título.",
    )
    ano = models.PositiveSmallIntegerField(null=True, blank=True)
    numero_edital = models.CharField(max_length=40, blank=True)
    situacao = models.CharField(max_length=12, choices=Situacao.choices, default=Situacao.PREVISTO)
    maturidade = models.CharField(max_length=14, choices=Maturidade.choices, default=Maturidade.EDITAL)
    url_oficial = models.URLField(max_length=500, blank=True)
    inscricoes_inicio = models.DateTimeField(null=True, blank=True)
    inscricoes_fim = models.DateTimeField(null=True, blank=True)
    vagas_total = models.PositiveIntegerField(null=True, blank=True)
    remuneracao_maxima = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    areas = models.ManyToManyField(
        AreaAtuacao,
        blank=True,
        related_name="concursos",
        help_text="União das áreas dos cargos com as regras aplicadas ao título/órgão.",
    )
    areas_manuais = models.BooleanField(
        default=False, help_text="Marcado quando você ajusta as áreas à mão; a classificação automática não mexe mais."
    )
    atributos = models.JSONField(default=dict, blank=True)
    revisado = models.BooleanField(default=False, help_text="Marque depois de conferir os dados com o edital.")
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-atualizado_em"]

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        if self.orgao_id and self.orgao.esfera:
            self.esfera = self.orgao.esfera
        elif not self.esfera:
            from .inferencia import inferir_esfera

            self.esfera = inferir_esfera(self.titulo)
        super().save(*args, **kwargs)


class Escolaridade(models.TextChoices):
    FUNDAMENTAL = "fundamental", "Fundamental"
    MEDIO = "medio", "Médio"
    TECNICO = "tecnico", "Técnico"
    SUPERIOR = "superior", "Superior"


class Cargo(models.Model):
    concurso = models.ForeignKey(Concurso, on_delete=models.CASCADE, related_name="cargos")
    codigo_externo = models.CharField(max_length=40, blank=True)
    nome = models.CharField(max_length=400)
    carreira = models.CharField(max_length=200, blank=True)
    areas = models.ManyToManyField(AreaAtuacao, blank=True, related_name="cargos")
    areas_manuais = models.BooleanField(
        default=False, help_text="Marcado quando você ajusta as áreas à mão; a classificação automática não mexe mais."
    )
    escolaridade = models.CharField(max_length=12, choices=Escolaridade.choices, blank=True)
    remuneracao = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    atributos = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["concurso", "codigo_externo", "nome"]
        unique_together = [("concurso", "nome")]

    def __str__(self):
        return self.nome


class Modalidade(models.TextChoices):
    TOTAL = "total", "Total"
    AMPLA = "ampla", "Ampla concorrência"
    PCD = "pcd", "Pessoas com deficiência"
    NEGROS = "negros", "Pessoas negras"
    INDIGENAS = "indigenas", "Indígenas"
    QUILOMBOLAS = "quilombolas", "Quilombolas"


class Vaga(models.Model):
    cargo = models.ForeignKey(Cargo, on_delete=models.CASCADE, related_name="vagas")
    localidade = models.CharField(max_length=200, blank=True, help_text="Vazio = nacional/única.")
    modalidade = models.CharField(max_length=12, choices=Modalidade.choices, default=Modalidade.TOTAL)
    quantidade = models.PositiveIntegerField(null=True, blank=True)
    cadastro_reserva = models.PositiveIntegerField(null=True, blank=True)
    atributos = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = [("cargo", "localidade", "modalidade")]

    def __str__(self):
        local = f" — {self.localidade}" if self.localidade else ""
        return f"{self.cargo}{local} ({self.get_modalidade_display()})"


class Etapa(models.Model):
    class Tipo(models.TextChoices):
        OBJETIVA = "objetiva", "Prova objetiva"
        DISCURSIVA = "discursiva", "Prova discursiva"
        TAF = "taf", "Teste de aptidão física"
        TITULOS = "titulos", "Avaliação de títulos"
        ORAL = "oral", "Prova oral"
        FORMACAO = "formacao", "Curso de formação"
        OUTRA = "outra", "Outra"

    concurso = models.ForeignKey(Concurso, on_delete=models.CASCADE, related_name="etapas")
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    peso = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    nota_maxima = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    eliminatoria = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.concurso} — {self.get_tipo_display()}"


class Evento(models.Model):
    """Datas do cronograma: alimentam o calendário (ICS) e os avisos."""

    class Tipo(models.TextChoices):
        INSCRICAO = "inscricao", "Inscrições"
        ISENCAO = "isencao", "Pedido de isenção"
        PROVA = "prova", "Prova"
        GABARITO = "gabarito", "Gabarito"
        RESULTADO = "resultado", "Resultado"
        RECURSO = "recurso", "Recursos"
        OUTRO = "outro", "Outro"

    concurso = models.ForeignKey(Concurso, on_delete=models.CASCADE, related_name="eventos")
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    descricao = models.CharField(max_length=300, blank=True)
    inicio = models.DateTimeField()
    fim = models.DateTimeField(null=True, blank=True)
    documento = models.ForeignKey("ingestao.Documento", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["inicio"]

    def __str__(self):
        return f"{self.concurso} — {self.get_tipo_display()} ({self.inicio:%d/%m/%Y})"


class Estatistica(models.Model):
    class Metrica(models.TextChoices):
        INSCRITOS = "inscritos", "Inscritos"
        CANDIDATOS_POR_VAGA = "cpv", "Candidatos por vaga"
        PRESENTES = "presentes", "Presentes"
        ABSTENCAO = "abstencao", "Abstenção (%)"
        CORTE_FINAL = "corte_final", "Nota de corte final"
        CORTE_ETAPA = "corte_etapa", "Nota de corte de etapa"
        CORTE_ESPERADO = "corte_esperado", "Nota de corte esperada"

    class Tipo(models.TextChoices):
        OFICIAL = "oficial", "Oficial"
        ESTIMADO = "estimado", "Estimado"

    vaga = models.ForeignKey(Vaga, on_delete=models.CASCADE, null=True, blank=True, related_name="estatisticas")
    cargo = models.ForeignKey(Cargo, on_delete=models.CASCADE, null=True, blank=True, related_name="estatisticas")
    metrica = models.CharField(max_length=16, choices=Metrica.choices)
    valor = models.DecimalField(max_digits=12, decimal_places=4)
    valor_min = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    valor_max = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.OFICIAL)
    documento = models.ForeignKey("ingestao.Documento", on_delete=models.SET_NULL, null=True, blank=True)
    calculado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "estatística"

    def __str__(self):
        alvo = self.vaga or self.cargo
        return f"{alvo}: {self.get_metrica_display()} = {self.valor}"


class AtributoDefinicao(models.Model):
    """Parâmetros extensíveis: cadastrar aqui cria um campo/filtro sem migração."""

    class Tipo(models.TextChoices):
        BOOL = "bool", "Sim/não"
        INTEIRO = "int", "Número inteiro"
        DECIMAL = "decimal", "Número decimal"
        TEXTO = "texto", "Texto"
        ESCOLHA = "escolha", "Escolha"

    class Entidade(models.TextChoices):
        CONCURSO = "concurso", "Concurso"
        CARGO = "cargo", "Cargo"
        VAGA = "vaga", "Vaga"

    chave = models.SlugField(max_length=60, unique=True, help_text="Ex.: exige_cnh")
    rotulo = models.CharField(max_length=120)
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.BOOL)
    entidade = models.CharField(max_length=10, choices=Entidade.choices, default=Entidade.CONCURSO)
    unidade = models.CharField(max_length=20, blank=True)
    opcoes = models.JSONField(default=list, blank=True, help_text="Para o tipo Escolha.")
    filtravel = models.BooleanField(default=True, help_text="Aparece como filtro no admin.")

    class Meta:
        verbose_name = "definição de atributo"
        verbose_name_plural = "definições de atributo"
        ordering = ["entidade", "rotulo"]

    def __str__(self):
        return f"{self.rotulo} ({self.get_entidade_display()})"


class FiltroAlerta(models.Model):
    """O que você quer acompanhar. Um evento novo que case com um filtro gera aviso."""

    nome = models.CharField(max_length=120)
    ativo = models.BooleanField(default=True)
    bancas = models.ManyToManyField(Banca, blank=True)
    areas = models.ManyToManyField(AreaAtuacao, blank=True)
    esferas = models.JSONField(default=list, blank=True, help_text='Ex.: ["federal", "distrital"]. Vazio = todas.')
    palavras_chave = models.JSONField(
        default=list, blank=True, help_text='Procuradas no título do concurso/documento. Ex.: ["TJ", "auditor"].'
    )
    tipos_documento = models.JSONField(
        default=list, blank=True, help_text='Ex.: ["edital_abertura", "retificacao"]. Vazio = todos.'
    )

    class Meta:
        verbose_name = "filtro de alerta"
        verbose_name_plural = "filtros de alerta"

    def __str__(self):
        return self.nome
