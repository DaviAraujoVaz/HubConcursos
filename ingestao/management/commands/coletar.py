from datetime import date

from django.core.management.base import BaseCommand, CommandError

from ingestao.adaptadores import adaptadores_registrados
from ingestao.coleta import executar
from ingestao.models import Execucao, Fonte


class Command(BaseCommand):
    help = "Coleta concursos e documentos de uma ou mais fontes (dou, cebraspe, fgv) ou de todas."

    def add_arguments(self, parser):
        parser.add_argument("fontes", nargs="+", help=f"Uma ou mais de: {', '.join(adaptadores_registrados())}, ou 'todas'.")
        parser.add_argument("--encerrados", action="store_true", help="Inclui concursos encerrados (histórico; demora mais).")
        parser.add_argument("--apenas", nargs="*", default=None, help="Só estes identificadores (ex.: CGU_26_AFFC, concursos/tjpb26).")
        parser.add_argument("--sem-arquivos", action="store_true", help="Não baixa PDFs; só registra os links.")
        parser.add_argument("--de", dest="data_inicio", help="DOU: data inicial AAAA-MM-DD (padrão: hoje).")
        parser.add_argument("--ate", dest="data_fim", help="DOU: data final AAAA-MM-DD (padrão: hoje).")
        parser.add_argument("--secoes", help="DOU: seções separadas por vírgula (padrão: DO1,DO2,DO3 e extras).")

    def handle(self, *args, **opcoes):
        fontes = opcoes["fontes"]
        if fontes == ["todas"]:
            ativas = set(Fonte.objects.filter(ativa=True).values_list("slug", flat=True))
            fontes = [s for s in adaptadores_registrados() if s in ativas]
        desconhecidas = set(fontes) - set(adaptadores_registrados())
        if desconhecidas:
            raise CommandError(f"Fontes desconhecidas: {', '.join(sorted(desconhecidas))}")

        extras = {
            "incluir_encerrados": opcoes["encerrados"],
            "apenas": opcoes["apenas"],
        }
        if opcoes["data_inicio"]:
            extras["data_inicio"] = date.fromisoformat(opcoes["data_inicio"])
        if opcoes["data_fim"]:
            extras["data_fim"] = date.fromisoformat(opcoes["data_fim"])
        if opcoes["secoes"]:
            extras["secoes"] = [s.strip().upper() for s in opcoes["secoes"].split(",") if s.strip()]

        falhas = 0
        for slug in fontes:
            self.stdout.write(f"→ {slug}")
            execucao = executar(slug, baixar_arquivos=not opcoes["sem_arquivos"], **extras)
            resumo = (
                f"  {execucao.concursos_vistos} concursos vistos, {execucao.concursos_novos} novos, "
                f"{execucao.documentos_novos} documentos novos"
            )
            if execucao.status == Execucao.Status.OK:
                self.stdout.write(self.style.SUCCESS(resumo))
            else:
                falhas += 1
                self.stdout.write(self.style.ERROR(f"{resumo}\n  ERRO: {execucao.erro}"))
        if falhas:
            raise CommandError(f"{falhas} fonte(s) falharam; veja Execuções no admin.")
