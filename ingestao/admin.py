from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from catalogo.models import Concurso, Maturidade, Situacao

from .models import Documento, EventoDominio, Execucao, Fonte, TipoDocumento


@admin.register(Fonte)
class FonteAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "ativa", "saude", "ultima_execucao", "ultimo_sucesso")
    list_editable = ("ativa",)
    readonly_fields = ("ultima_execucao", "ultimo_sucesso", "ultimo_erro")

    @admin.display(description="Saúde")
    def saude(self, obj):
        if obj.ultimo_erro:
            return format_html('<span style="color:#b42318">✖ erro</span>')
        if not obj.ultimo_sucesso:
            return "nunca rodou"
        horas = (timezone.now() - obj.ultimo_sucesso).total_seconds() / 3600
        if horas > 48:
            return format_html('<span style="color:#b54708">⚠ sem sucesso há {} h</span>', int(horas))
        return format_html('<span style="color:#067647">✔ ok</span>')


@admin.register(Execucao)
class ExecucaoAdmin(admin.ModelAdmin):
    list_display = ("fonte", "inicio", "fim", "status", "concursos_vistos", "concursos_novos", "documentos_novos")
    list_filter = ("fonte", "status")
    readonly_fields = [f.name for f in Execucao._meta.fields]

    def has_add_permission(self, request):
        return False


class SoltosFilter(admin.SimpleListFilter):
    title = "vinculado a concurso"
    parameter_name = "vinculado"

    def lookups(self, request, model_admin):
        return [("nao", "Não (precisa vincular)"), ("sim", "Sim")]

    def queryset(self, request, queryset):
        if self.value() == "nao":
            return queryset.filter(concurso__isnull=True)
        if self.value() == "sim":
            return queryset.filter(concurso__isnull=False)
        return queryset


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ("titulo_curto", "tipo", "fonte", "concurso", "publicado_em", "precisa_revisao", "abrir")
    list_filter = ("fonte", "tipo", SoltosFilter, "precisa_revisao", "concurso__banca")
    search_fields = ("titulo", "texto", "chave_externa")
    autocomplete_fields = ("concurso",)
    readonly_fields = ("fonte", "chave_externa", "url", "publicado_em", "sha256", "arquivo", "metadados", "criado_em")
    date_hierarchy = "publicado_em"
    actions = ["criar_concurso", "marcar_revisado"]
    list_per_page = 50

    @admin.display(description="Título")
    def titulo_curto(self, obj):
        return obj.titulo[:110]

    @admin.display(description="")
    def abrir(self, obj):
        return format_html('<a href="{}" target="_blank" rel="noopener">abrir</a>', obj.url) if obj.url else ""

    @admin.action(description="Criar concurso a partir do documento (ex.: autorização/edital no DOU)")
    def criar_concurso(self, request, queryset):
        criados = 0
        for doc in queryset.filter(concurso__isnull=True):
            situacao, maturidade = Situacao.PREVISTO, Maturidade.EDITAL
            if doc.tipo == TipoDocumento.AUTORIZACAO:
                situacao, maturidade = Situacao.AUTORIZADO, Maturidade.AUTORIZADO
            elif doc.tipo == TipoDocumento.CONTRATACAO_BANCA:
                situacao, maturidade = Situacao.AUTORIZADO, Maturidade.BANCA
            concurso = Concurso.objects.create(
                chave_externa=f"manual:{doc.fonte.slug}:{doc.pk}",
                titulo=doc.titulo[:400],
                situacao=situacao,
                maturidade=maturidade,
                url_oficial=doc.url,
                ano=doc.publicado_em.year if doc.publicado_em else None,
            )
            doc.concurso = concurso
            doc.save(update_fields=["concurso"])
            criados += 1
        self.message_user(request, f"{criados} concursos criados. Abra cada um para completar órgão e banca.", messages.SUCCESS)

    @admin.action(description="Marcar como revisado")
    def marcar_revisado(self, request, queryset):
        queryset.update(precisa_revisao=False)


@admin.register(EventoDominio)
class EventoDominioAdmin(admin.ModelAdmin):
    list_display = ("tipo", "concurso", "documento", "criado_em", "processado_em")
    list_filter = ("tipo", ("processado_em", admin.EmptyFieldListFilter))
    readonly_fields = [f.name for f in EventoDominio._meta.fields]

    def has_add_permission(self, request):
        return False
