"""Regras de área que faltaram na primeira coleta real (01/11/2026).

Títulos como "Secretaria de Estado da Educação de Alagoas" e "Agência Reguladora
de Serviços Públicos do Estado de Alagoas" ficavam sem área.
"""
from django.db import migrations

# área: termos no título/órgão
REGRAS_ORGAO = {
    "educacao": ["secretaria de estado da educacao", "secretaria de estado de educacao", "secretaria municipal de educacao"],
    "saude": ["secretaria de estado da saude", "secretaria de estado de saude", "secretaria municipal de saude"],
    "fiscal": ["secretaria de estado da fazenda", "secretaria de estado de fazenda", "secretaria municipal de fazenda"],
    "regulacao": ["agencia reguladora*"],
    # FGV não estrutura cargos; estes vêm do título.
    "policial": ["guarda municipal", "seguranca municipal", "administracao penitenciaria"],
    "controle": ["auditoria-geral", "auditoria geral"],
}


def criar(apps, schema_editor):
    AreaAtuacao = apps.get_model("catalogo", "AreaAtuacao")
    RegraArea = apps.get_model("catalogo", "RegraArea")
    for slug, termos in REGRAS_ORGAO.items():
        area = AreaAtuacao.objects.filter(slug=slug).first()
        if area is None:  # área removida no admin
            continue
        for termo in termos:
            RegraArea.objects.get_or_create(termo=termo, alvo="orgao", area=area)


class Migration(migrations.Migration):
    dependencies = [("catalogo", "0003_dados_iniciais")]
    operations = [migrations.RunPython(criar, migrations.RunPython.noop)]
