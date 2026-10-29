from django.contrib import admin, messages
from django.db.models import Count
from django.utils.html import format_html

from ingestao.models import Documento

from .classificacao import classificar_concurso
from .models import (
    AreaAtuacao,
    AtributoDefinicao,
    Banca,
    Cargo,
    Concurso,
    Estatistica,
    Etapa,
    Evento,
    FiltroAlerta,
    Orgao,
    RegraArea,
    Vaga,
)


# --- Filtros ------------------------------------------------------------------

class AreaFilter(admin.SimpleListFilter):
    title = "área de atuação"
    parameter_name = "area"

    def lookups(self, request, model_admin):
        return [(a.slug, a.nome) for a in AreaAtuacao.objects.all()]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(areas__slug=self.value()).distinct()
        return queryset


def filtro_de_atributo(definicao: AtributoDefinicao, prefixo: str = ""):
    """Cria um filtro do admin a partir de uma AtributoDefinicao (sem migração)."""
    caminho = f"{prefixo}atributos__{definicao.chave}"

    class FiltroAtributo(admin.SimpleListFilter):
        title = definicao.rotulo
        parameter_name = f"attr_{definicao.chave}"

        def lookups(self, request, model_admin):
            if definicao.tipo == AtributoDefinicao.Tipo.BOOL:
                return [("1", "Sim"), ("0", "Não")]
            if definicao.tipo == AtributoDefinicao.Tipo.ESCOLHA:
                return [(str(o), str(o)) for o in definicao.opcoes]
            valores = (
                model_admin.get_queryset(request)
                .exclude(**{f"{caminho}__isnull": True})
                .values_list(caminho, flat=True)
                .distinct()[:30]
            )
            return [(str(v), str(v)) for v in valores if v not in (None, "")]

        def queryset(self, request, queryset):
            valor = self.value()
            if valor is None:
                return queryset
            if definicao.tipo == AtributoDefinicao.Tipo.BOOL:
                valor = valor == "1"
            elif definicao.tipo == AtributoDefinicao.Tipo.INTEIRO:
                valor = int(valor)
            return queryset.filter(**{caminho: valor}).distinct()

    FiltroAtributo.__name__ = f"Filtro_{definicao.chave}"
    return FiltroAtributo


class FiltrosDinamicosMixin:
    """Acrescenta aos filtros fixos os atributos marcados como filtráveis."""

    entidade_atributos = AtributoDefinicao.Entidade.CONCURSO
    prefixos = {AtributoDefinicao.Entidade.CONCURSO: ""}

    def get_list_filter(self, request):
        fixos = list(super().get_list_filter(request))
        dinamicos = []
        for definicao in AtributoDefinicao.objects.filter(filtravel=True):
            prefixo = self.prefixos.get(definicao.entidade)
            if prefixo is not None:
                dinamicos.append(filtro_de_atributo(definicao, prefixo))
        return fixos + dinamicos


# --- Concurso -----------------------------------------------------------------

class CargoInline(admin.TabularInline):
    model = Cargo
    extra = 0
    fields = ("codigo_externo", "nome", "areas_texto", "escolaridade", "remuneracao", "link")
    readonly_fields = ("areas_texto", "link")
    show_change_link = True

    @admin.display(description="Áreas")
    def areas_texto(self, obj):
        return ", ".join(a.nome for a in obj.areas.all()) or "—"

    @admin.display(description="")
    def link(self, obj):
        return format_html('<a href="/admin/catalogo/cargo/{}/change/">editar áreas/vagas</a>', obj.pk) if obj.pk else ""


class DocumentoInline(admin.TabularInline):
    model = Documento
    extra = 0
    fields = ("publicado_em", "tipo", "titulo_link", "precisa_revisao")
    readonly_fields = ("publicado_em", "tipo", "titulo_link", "precisa_revisao")
    can_delete = False
    show_change_link = True
    ordering = ("-publicado_em",)

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Documento")
    def titulo_link(self, obj):
        if obj.url:
            return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', obj.url, obj.titulo[:140])
        return obj.titulo[:140]


class EventoInline(admin.TabularInline):
    model = Evento
    extra = 0
    fields = ("tipo", "descricao", "inicio", "fim")


class EtapaInline(admin.TabularInline):
    model = Etapa
    extra = 0


@admin.register(Concurso)
class ConcursoAdmin(FiltrosDinamicosMixin, admin.ModelAdmin):
    list_display = (
        "titulo",
        "banca",
        "esfera",
        "areas_texto",
        "situacao",
        "inscricoes_fim",
        "vagas_total",
        "remuneracao_maxima",
        "n_documentos",
        "revisado",
        "site",
    )
    list_filter = ("banca", "esfera", AreaFilter, "situacao", "maturidade", "revisado", "ano")
    search_fields = ("titulo", "chave_externa", "orgao__nome", "orgao__sigla", "cargos__nome")
    autocomplete_fields = ("orgao",)
    filter_horizontal = ("areas",)
    readonly_fields = ("chave_externa", "criado_em", "atualizado_em")
    inlines = [CargoInline, EventoInline, EtapaInline, DocumentoInline]
    date_hierarchy = "inscricoes_fim"
    list_per_page = 50
    actions = ["marcar_revisado", "reclassificar_areas"]
    fieldsets = (
        (None, {"fields": ("titulo", "orgao", "banca", "esfera", "situacao", "maturidade", "revisado")}),
        ("Áreas de atuação", {"fields": ("areas", "areas_manuais")}),
        ("Detalhes", {"fields": ("ano", "numero_edital", "url_oficial", "inscricoes_inicio", "inscricoes_fim", "vagas_total", "remuneracao_maxima")}),
        ("Atributos extras e notas", {"fields": ("atributos", "observacoes"), "classes": ("collapse",)}),
        ("Origem", {"fields": ("chave_externa", "criado_em", "atualizado_em"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("banca", "orgao")
            .prefetch_related("areas")
            .annotate(_n_documentos=Count("documentos", distinct=True))
        )

    @admin.display(description="Áreas")
    def areas_texto(self, obj):
        return ", ".join(sorted(a.nome for a in obj.areas.all())) or "—"

    def save_related(self, request, form, formsets, change):
        antes = set(form.instance.areas.values_list("id", flat=True)) if change else set()
        super().save_related(request, form, formsets, change)
        depois = set(form.instance.areas.values_list("id", flat=True))
        if change and antes != depois and not form.instance.areas_manuais:
            Concurso.objects.filter(pk=form.instance.pk).update(areas_manuais=True)
            self.message_user(request, "Áreas ajustadas à mão; a classificação automática não mexe mais neste concurso.", messages.INFO)

    @admin.display(description="Docs", ordering="_n_documentos")
    def n_documentos(self, obj):
        return obj._n_documentos

    @admin.display(description="Site")
    def site(self, obj):
        return format_html('<a href="{}" target="_blank" rel="noopener">abrir</a>', obj.url_oficial) if obj.url_oficial else ""

    @admin.action(description="Marcar como revisado (a coleta não sobrescreve mais os dados)")
    def marcar_revisado(self, request, queryset):
        total = queryset.update(revisado=True)
        self.message_user(request, f"{total} concursos marcados como revisados.", messages.SUCCESS)

    @admin.action(description="Reaplicar regras de área aos cargos")
    def reclassificar_areas(self, request, queryset):
        alterados = sum(classificar_concurso(c) for c in queryset.prefetch_related("cargos"))
        self.message_user(request, f"{alterados} concursos tiveram as áreas atualizadas.", messages.SUCCESS)


# --- Cargo e vagas ------------------------------------------------------------

class VagaInline(admin.TabularInline):
    model = Vaga
    extra = 0


@admin.register(Cargo)
class CargoAdmin(FiltrosDinamicosMixin, admin.ModelAdmin):
    prefixos = {AtributoDefinicao.Entidade.CARGO: ""}
    list_display = ("nome", "concurso", "areas_texto", "escolaridade", "remuneracao", "areas_manuais")
    list_filter = (AreaFilter, "concurso__banca", "concurso__esfera", "escolaridade", "areas_manuais")
    search_fields = ("nome", "concurso__titulo")
    autocomplete_fields = ("concurso",)
    filter_horizontal = ("areas",)
    inlines = [VagaInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("concurso").prefetch_related("areas")

    @admin.display(description="Áreas")
    def areas_texto(self, obj):
        return ", ".join(a.nome for a in obj.areas.all()) or "—"

    def save_related(self, request, form, formsets, change):
        antes = set(form.instance.areas.values_list("id", flat=True)) if change else set()
        super().save_related(request, form, formsets, change)
        depois = set(form.instance.areas.values_list("id", flat=True))
        if antes != depois:
            # As áreas do concurso são a união das dos cargos: recalcula.
            classificar_concurso(form.instance.concurso, incluir_cargos=False)
        if change and antes != depois and not form.instance.areas_manuais:
            # Você corrigiu à mão: a classificação automática não mexe mais neste cargo.
            Cargo.objects.filter(pk=form.instance.pk).update(areas_manuais=True)
            self.message_user(
                request,
                "Áreas ajustadas à mão. Se quiser que isso valha para cargos parecidos, crie uma Regra de área.",
                messages.INFO,
            )


# --- Cadastros ----------------------------------------------------------------

@admin.register(Orgao)
class OrgaoAdmin(admin.ModelAdmin):
    list_display = ("nome", "sigla", "esfera", "poder", "uf", "cnpj")
    list_filter = ("esfera", "poder", "uf")
    search_fields = ("nome", "sigla", "cnpj")


@admin.register(Banca)
class BancaAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "site")
    prepopulated_fields = {"slug": ("nome",)}
    search_fields = ("nome",)


class RegraAreaInline(admin.TabularInline):
    model = RegraArea
    extra = 1


@admin.register(AreaAtuacao)
class AreaAtuacaoAdmin(admin.ModelAdmin):
    list_display = ("nome", "descricao", "n_regras", "n_cargos")
    prepopulated_fields = {"slug": ("nome",)}
    search_fields = ("nome",)
    inlines = [RegraAreaInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_r=Count("regras", distinct=True), _c=Count("cargos", distinct=True))

    @admin.display(description="Regras", ordering="_r")
    def n_regras(self, obj):
        return obj._r

    @admin.display(description="Cargos", ordering="_c")
    def n_cargos(self, obj):
        return obj._c


@admin.register(RegraArea)
class RegraAreaAdmin(admin.ModelAdmin):
    list_display = ("termo", "alvo", "area", "ativa")
    list_filter = ("area", "alvo", "ativa")
    list_editable = ("ativa",)
    search_fields = ("termo",)


@admin.register(AtributoDefinicao)
class AtributoDefinicaoAdmin(admin.ModelAdmin):
    list_display = ("rotulo", "chave", "tipo", "entidade", "filtravel")
    list_filter = ("entidade", "tipo", "filtravel")


@admin.register(FiltroAlerta)
class FiltroAlertaAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo")
    filter_horizontal = ("bancas", "areas")


@admin.register(Estatistica)
class EstatisticaAdmin(admin.ModelAdmin):
    list_display = ("__str__", "metrica", "tipo", "valor", "calculado_em")
    list_filter = ("metrica", "tipo")
    autocomplete_fields = ("cargo",)
    raw_id_fields = ("vaga", "documento")
