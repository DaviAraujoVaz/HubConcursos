"""Roda um adaptador do começo ao fim, registrando a execução e a saúde da fonte."""
import logging
import traceback

from django.utils import timezone

from .models import EventoDominio, Execucao, Fonte
from .persistencia import Contagem, emitir, persistir

log = logging.getLogger(__name__)


def executar(slug: str, baixar_arquivos: bool | None = None, **opcoes) -> Execucao:
    from .adaptadores import REGISTRO

    if slug not in REGISTRO:
        raise ValueError(f"Fonte desconhecida: {slug}. Disponíveis: {', '.join(sorted(REGISTRO))}")
    classe = REGISTRO[slug]
    fonte, _ = Fonte.objects.get_or_create(slug=slug, defaults={"nome": classe.nome})
    # A primeira coleta traz o acervo todo da fonte; avisar sobre ele seria uma enxurrada.
    primeira = fonte.ultimo_sucesso is None
    execucao = Execucao.objects.create(fonte=fonte)
    fonte.ultima_execucao = timezone.now()
    fonte.save(update_fields=["ultima_execucao"])

    total = Contagem()
    try:
        adaptador = classe()
        for resultado in adaptador.coletar(**opcoes):
            total.somar(persistir(fonte, adaptador, resultado, baixar_arquivos))
    except Exception as erro:
        log.exception("Coleta de %s falhou", slug)
        execucao.status = Execucao.Status.ERRO
        execucao.erro = "".join(traceback.format_exception_only(type(erro), erro)).strip()[:2000]
        fonte.ultimo_erro = execucao.erro
        fonte.save(update_fields=["ultimo_erro"])
        emitir(EventoDominio.Tipo.COLETA_FALHOU, fonte=slug, erro=execucao.erro[:500])
    else:
        execucao.status = Execucao.Status.OK
        fonte.ultimo_sucesso = timezone.now()
        fonte.ultimo_erro = ""
        fonte.save(update_fields=["ultimo_sucesso", "ultimo_erro"])
    finally:
        execucao.fim = timezone.now()
        execucao.concursos_vistos = total.concursos_vistos
        execucao.concursos_novos = total.concursos_novos
        execucao.documentos_novos = total.documentos_novos
        execucao.save()
        if primeira:
            silenciar_eventos(slug, desde=execucao.inicio)
    log.info(
        "%s: %d concursos vistos, %d novos, %d documentos novos (%s)",
        slug,
        total.concursos_vistos,
        total.concursos_novos,
        total.documentos_novos,
        execucao.get_status_display(),
    )
    return execucao


def silenciar_eventos(slug: str, desde) -> int:
    """Marca como lidos, sem aviso, os eventos da fonte criados desde `desde`.
    Falhas de coleta continuam avisando."""
    return (
        EventoDominio.objects.filter(processado_em__isnull=True, criado_em__gte=desde, payload__fonte=slug)
        .exclude(tipo=EventoDominio.Tipo.COLETA_FALHOU)
        .update(processado_em=timezone.now())
    )
