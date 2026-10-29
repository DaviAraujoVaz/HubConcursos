from django.core.management.base import BaseCommand

from catalogo.classificacao import reclassificar_todos


class Command(BaseCommand):
    help = "Reaplica as regras de área a todos os cargos (exceto os ajustados à mão)."

    def handle(self, *args, **opcoes):
        alterados = reclassificar_todos()
        self.stdout.write(self.style.SUCCESS(f"{alterados} cargos tiveram as áreas atualizadas."))
