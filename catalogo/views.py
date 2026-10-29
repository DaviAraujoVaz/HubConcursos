"""Calendário (ICS) com inscrições e eventos dos concursos não encerrados.

Assine no celular/Google Agenda: http://SEU_HOST/calendario.ics?token=CALENDARIO_TOKEN
O token evita que qualquer pessoa na rede leia sua agenda.
"""
import os
from datetime import timedelta
from datetime import timezone as dt_timezone

from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone

from .models import Concurso, Evento, Situacao


def _escapar(texto: str) -> str:
    return (texto or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _data(valor) -> str:
    return valor.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _vevent(uid, inicio, fim, resumo, descricao="", url=""):
    linhas = [
        "BEGIN:VEVENT",
        f"UID:{uid}@concursohub",
        f"DTSTAMP:{_data(timezone.now())}",
        f"DTSTART:{_data(inicio)}",
        f"DTEND:{_data(fim or inicio + timedelta(hours=1))}",
        f"SUMMARY:{_escapar(resumo)}",
    ]
    if descricao:
        linhas.append(f"DESCRIPTION:{_escapar(descricao)}")
    if url:
        linhas.append(f"URL:{url}")
    linhas.append("END:VEVENT")
    return linhas


def gerar_ics() -> str:
    linhas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ConcursoHub//PT-BR", "X-WR-CALNAME:Concursos"]
    ativos = Concurso.objects.exclude(situacao__in=[Situacao.ENCERRADO, Situacao.HOMOLOGADO])
    for concurso in ativos.filter(inscricoes_fim__isnull=False):
        # Um lembrete no último dia de inscrição vale mais que um bloco de semanas.
        linhas += _vevent(
            f"inscricao-fim-{concurso.pk}",
            concurso.inscricoes_fim - timedelta(hours=1),
            concurso.inscricoes_fim,
            f"Último dia de inscrição: {concurso.titulo}",
            url=concurso.url_oficial,
        )
    for evento in Evento.objects.filter(concurso__in=ativos).select_related("concurso"):
        linhas += _vevent(
            f"evento-{evento.pk}",
            evento.inicio,
            evento.fim,
            f"{evento.get_tipo_display()}: {evento.concurso.titulo}",
            evento.descricao,
            evento.concurso.url_oficial,
        )
    linhas.append("END:VCALENDAR")
    return "\r\n".join(linhas) + "\r\n"


def calendario(request):
    token = os.environ.get("CALENDARIO_TOKEN", "")
    if token and request.GET.get("token") != token:
        return HttpResponseForbidden("token inválido")
    return HttpResponse(gerar_ics(), content_type="text/calendar; charset=utf-8")
