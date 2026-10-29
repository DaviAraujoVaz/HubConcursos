from django.db import migrations

FONTES = [
    ("dou", "Diário Oficial da União (INLABS)"),
    ("cebraspe", "Cebraspe"),
    ("fgv", "FGV Conhecimento"),
]


def criar(apps, schema_editor):
    Fonte = apps.get_model("ingestao", "Fonte")
    for slug, nome in FONTES:
        Fonte.objects.get_or_create(slug=slug, defaults={"nome": nome})


class Migration(migrations.Migration):
    dependencies = [("ingestao", "0001_initial")]
    operations = [migrations.RunPython(criar, migrations.RunPython.noop)]
