from django.core.management.base import BaseCommand
from django.utils import timezone

from ingestao.avisos import processar
from ingestao.models import EventoDominio


class Command(BaseCommand):
    help = "Envia avisos (Telegram ou log) dos eventos novos que casam com seus filtros de alerta."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=15, help="Ignora documentos publicados há mais de N dias.")
        parser.add_argument(
            "--silenciar-pendentes",
            action="store_true",
            help="Marca tudo que está pendente como lido, sem avisar. Use depois da primeira coleta.",
        )

    def handle(self, *args, **opcoes):
        if opcoes["silenciar_pendentes"]:
            total = EventoDominio.objects.filter(processado_em__isnull=True).update(processado_em=timezone.now())
            self.stdout.write(self.style.SUCCESS(f"{total} eventos marcados como lidos."))
            return
        processados, enviados = processar(dias_documento=opcoes["dias"])
        self.stdout.write(self.style.SUCCESS(f"{processados} eventos processados, {enviados} avisos enviados."))
