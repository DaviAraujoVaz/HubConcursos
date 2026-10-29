"""Transforma eventos de domínio em avisos (Telegram ou log).

Um evento vira aviso quando casa com pelo menos um FiltroAlerta ativo.
Falhas de coleta sempre avisam. Sem filtros cadastrados, nada é enviado
(exceto falhas), para não inundar você na primeira coleta.
"""
import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from catalogo.models import FiltroAlerta

from .models import EventoDominio
from .texto import normalizar

log = logging.getLogger(__name__)

ROTULO = {
    EventoDominio.Tipo.CONCURSO_DESCOBERTO: "Novo concurso",
    EventoDominio.Tipo.CONCURSO_MUDOU_SITUACAO: "Concurso mudou de situação",
    EventoDominio.Tipo.DOCUMENTO_PUBLICADO: "Novo documento",
    EventoDominio.Tipo.COLETA_FALHOU: "Coleta falhou",
}


def casa(filtro: FiltroAlerta, evento: EventoDominio) -> bool:
    concurso = evento.concurso
    documento = evento.documento

    if filtro.tipos_documento and evento.tipo == EventoDominio.Tipo.DOCUMENTO_PUBLICADO:
        if not documento or documento.tipo not in filtro.tipos_documento:
            return False

    bancas = set(filtro.bancas.values_list("id", flat=True))
    if bancas and (not concurso or concurso.banca_id not in bancas):
        return False

    if filtro.esferas and (not concurso or concurso.esfera not in filtro.esferas):
        return False

    areas = set(filtro.areas.values_list("id", flat=True))
    if areas:
        if not concurso:
            return False
        areas_concurso = set(concurso.areas.values_list("id", flat=True))
        if not areas & areas_concurso:
            return False

    if filtro.palavras_chave:
        alvo = normalizar(" ".join(filter(None, [concurso.titulo if concurso else "", documento.titulo if documento else ""])))
        if not any(normalizar(p) in alvo for p in filtro.palavras_chave):
            return False
    return True


def mensagem(evento: EventoDominio) -> str:
    p = evento.payload or {}
    partes = [f"🔔 {ROTULO.get(evento.tipo, evento.tipo)}"]
    if evento.concurso:
        partes.append(evento.concurso.titulo)
    if evento.documento:
        partes.append(f"{evento.documento.get_tipo_display()}: {evento.documento.titulo}")
        if evento.documento.url:
            partes.append(evento.documento.url)
    elif evento.concurso and evento.concurso.url_oficial:
        partes.append(evento.concurso.url_oficial)
    if evento.tipo == EventoDominio.Tipo.CONCURSO_MUDOU_SITUACAO:
        partes.append(f"{p.get('de')} → {p.get('para')}")
    if evento.tipo == EventoDominio.Tipo.COLETA_FALHOU:
        partes.append(f"Fonte: {p.get('fonte')}\n{p.get('erro', '')}")
    return "\n".join(partes)


def enviar(texto: str) -> bool:
    if not (settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID):
        log.info("AVISO\n%s", texto)
        return True
    resposta = requests.post(
        f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
        # Texto puro: títulos e URLs têm "_" e "*" que quebrariam Markdown.
        data={"chat_id": settings.TELEGRAM_CHAT_ID, "text": texto, "disable_web_page_preview": True},
        timeout=20,
    )
    if not resposta.ok:
        log.warning("Telegram recusou o aviso: %s", resposta.text[:200])
    return resposta.ok


def processar(dias_documento: int = 15, enviar_fn=enviar) -> tuple[int, int]:
    """Processa eventos pendentes. Documentos publicados há mais de `dias_documento`
    dias não geram aviso (evita a enxurrada de arquivos antigos na primeira coleta).
    Devolve (eventos processados, avisos enviados)."""
    filtros = list(FiltroAlerta.objects.filter(ativo=True).prefetch_related("bancas", "areas"))
    limite = timezone.now() - timedelta(days=dias_documento)
    pendentes = EventoDominio.objects.filter(processado_em__isnull=True).select_related(
        "concurso", "concurso__banca", "documento"
    )
    processados = enviados = 0
    for evento in pendentes:
        avisar = False
        if evento.tipo == EventoDominio.Tipo.COLETA_FALHOU:
            avisar = True
        elif evento.tipo == EventoDominio.Tipo.DOCUMENTO_PUBLICADO and evento.documento and evento.documento.publicado_em and evento.documento.publicado_em < limite:
            avisar = False
        else:
            avisar = any(casa(f, evento) for f in filtros)
        if avisar and enviar_fn(mensagem(evento)):
            enviados += 1
        evento.processado_em = timezone.now()
        evento.save(update_fields=["processado_em"])
        processados += 1
    return processados, enviados
