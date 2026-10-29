from datetime import timedelta

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ingestao.adaptadores import adaptadores_registrados
from ingestao.models import Fonte

# O DOU sai uma vez por dia (mais edições extras); não precisa ser baixado a cada rodada.
INTERVALO_MINIMO = {"dou": timedelta(hours=6)}


class Command(BaseCommand):
    help = "O que o agendador roda: coleta as fontes ativas (respeitando intervalos) e envia os avisos."

    def handle(self, *args, **opcoes):
        agora = timezone.now()
        fontes = []
        for fonte in Fonte.objects.filter(ativa=True, slug__in=list(adaptadores_registrados())):
            if fonte.slug == "dou" and not (settings.INLABS_EMAIL and settings.INLABS_SENHA):
                self.stdout.write("→ dou: sem INLABS_EMAIL/INLABS_SENHA no .env, pulando")
                continue
            intervalo = INTERVALO_MINIMO.get(fonte.slug)
            if intervalo and fonte.ultimo_sucesso and agora - fonte.ultimo_sucesso < intervalo:
                self.stdout.write(f"→ {fonte.slug}: coletado há pouco, pulando")
                continue
            fontes.append(fonte.slug)
        if fontes:
            try:
                call_command("coletar", *fontes, stdout=self.stdout, stderr=self.stderr)
            except CommandError as erro:
                # Uma fonte com problema não impede os avisos das outras (nem o aviso da falha).
                self.stderr.write(str(erro))
        call_command("avisar", stdout=self.stdout, stderr=self.stderr)
