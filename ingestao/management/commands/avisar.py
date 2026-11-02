from django.core.management.base import BaseCommand
from django.utils import timezone

from ingestao.avisos import processar
from ingestao.models import EventoDominio


class Command(BaseCommand):
    help = "Envia por e-mail o resumo do dia com os eventos que casam com seus filtros de alerta."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=15, help="Ignora documentos publicados há mais de N dias.")
        parser.add_argument(
            "--silenciar-pendentes",
            action="store_true",
            help="Marca tudo que está pendente como lido, sem avisar. Use depois de uma coleta grande.",
        )
        parser.add_argument(
            "--agora", action="store_true", help="Envia já, sem esperar o horário nem checar se o de hoje já saiu."
        )
        parser.add_argument("--previa", action="store_true", help="Mostra o resumo sem enviar nem marcar nada.")

    def handle(self, *args, **opcoes):
        if opcoes["silenciar_pendentes"]:
            total = EventoDominio.objects.filter(processado_em__isnull=True).update(processado_em=timezone.now())
            self.stdout.write(self.style.SUCCESS(f"{total} eventos marcados como lidos."))
            return
        resultado = processar(dias_documento=opcoes["dias"], forcar=opcoes["agora"], previa=opcoes["previa"])
        if opcoes["previa"]:
            self.stdout.write(resultado.motivo)
        elif resultado.resumo and not resultado.resumo.ok:
            self.stderr.write(self.style.ERROR(f"Resumo: {resultado.motivo}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Resumo: {resultado.motivo} ({resultado.processados} eventos processados)."))
