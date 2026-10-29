"""Bancas acompanhadas, taxonomia de áreas de atuação e regras de classificação.

Tudo aqui é editável depois no admin (Áreas de atuação → regras). Termos são
comparados sem acentos/maiúsculas, como palavra inteira; "*" no fim = prefixo.
"""
from django.db import migrations
from django.utils.text import slugify

BANCAS = [
    ("Cebraspe", "cebraspe", "https://www.cebraspe.org.br/concursos/", ["Cespe", "Cespe/UnB", "Cebraspe/UnB"]),
    ("FGV", "fgv", "https://conhecimento.fgv.br/concursos", ["FGV Conhecimento", "Fundação Getulio Vargas", "FGV Projetos"]),
]

# área: (descrição, termos no título/órgão, termos no nome do cargo)
AREAS = {
    "Tribunais": (
        "Poder Judiciário: TJs, TRFs, TRTs, TREs e tribunais superiores",
        ["tribunal de justica", "tribunal regional", "tribunal superior", "supremo tribunal", "justica federal",
         "justica do trabalho", "justica eleitoral", "justica militar",
         "tj", "tjdft", "trf", "trt", "tre", "tse", "tst", "stj", "stf", "stm", "cnj"],
        ["analista judiciario", "tecnico judiciario", "oficial de justica", "juiz*"],
    ),
    "Fiscal": (
        "Receitas e fazendas: auditores e fiscais de tributos",
        ["receita federal", "secretaria da fazenda", "secretaria de fazenda", "sefaz*", "fazenda estadual", "fazenda municipal"],
        ["auditor-fiscal", "auditor fiscal", "fiscal de tributos", "fiscal de rendas", "fiscal tributario",
         "auditor de tributos", "analista tributario", "agente fiscal"],
    ),
    "Controle": (
        "Tribunais de contas e controladorias",
        ["tribunal de contas", "tcu", "tce", "tcm", "tcdf", "cgu", "controladoria*"],
        ["auditor federal de financas e controle", "auditor de controle externo", "analista de controle*",
         "auditor de controle interno", "affc"],
    ),
    "Policial": (
        "Polícias, bombeiros e sistema penal",
        ["policia*", "pf", "prf", "pc", "pm", "pcdf", "pmdf", "cbm", "cbmdf", "corpo de bombeiros", "policia penal", "depen"],
        ["delegado*", "agente de policia", "escrivao", "perito criminal", "papiloscopista", "investigador*",
         "soldado", "policial*", "agente penitenciario", "policia penal"],
    ),
    "Bancária": (
        "Bancos públicos",
        ["banco do brasil", "caixa economica", "caixa", "bnb", "banco do nordeste", "bndes", "banco central",
         "bacen", "bcb", "basa", "banco da amazonia", "banrisul", "brb", "banestes"],
        ["escriturario", "tecnico bancario"],
    ),
    "Legislativo": (
        "Câmaras, assembleias e Senado",
        ["camara dos deputados", "senado", "assembleia legislativa", "camara municipal", "camara legislativa", "cldf", "cd"],
        ["analista legislativo", "consultor legislativo", "tecnico legislativo"],
    ),
    "Jurídica": (
        "Advocacia pública, Ministério Público e Defensoria",
        ["advocacia-geral da uniao", "agu", "pgfn", "pge", "pgm", "procuradoria*", "defensoria*", "dpu", "dpe",
         "ministerio publico", "mpu", "mpf", "mpt", "mpm"],
        ["procurador*", "advogado*", "defensor*", "promotor*", "analista juridico", "assessor juridico"],
    ),
    "Regulação": (
        "Agências reguladoras",
        ["agencia nacional", "anvisa", "anac", "anatel", "aneel", "anp", "ans", "antt", "antaq", "ana", "ancine", "anm"],
        ["especialista em regulacao", "analista em regulacao", "tecnico em regulacao"],
    ),
    "TI": (
        "Tecnologia da informação",
        [],
        ["tecnologia da informacao", "ti", "desenvolvimento de sistemas", "ciencia de dados", "banco de dados",
         "infraestrutura de ti", "seguranca da informacao", "analista de sistemas", "programador*", "informatica",
         "suporte tecnico", "governanca de ti", "inteligencia artificial", "engenharia de software",
         "analise de dados", "cientista de dados"],
    ),
    "Saúde": (
        "Profissionais de saúde",
        ["ebserh", "secretaria de saude", "secretaria da saude", "hospital*", "fundacao hospitalar"],
        ["medico*", "enfermeiro*", "enfermagem", "farmaceutico*", "odontolog*", "dentista", "fisioterapeut*",
         "nutricionista", "psicolog*", "fonoaudiolog*", "biomedic*", "terapeuta ocupacional", "assistente social"],
    ),
    "Educação": (
        "Professores e carreiras de ensino",
        ["seduc", "sedf", "seec", "secretaria de educacao", "secretaria da educacao", "universidade*", "instituto federal", "colegio pedro ii"],
        ["professor*", "pedagog*", "docente", "magisterio", "orientador educacional", "supervisor escolar"],
    ),
    "Administrativa": (
        "Carreiras administrativas de nível médio e superior",
        [],
        ["assistente administrativo", "auxiliar administrativo", "agente administrativo", "analista administrativo",
         "tecnico administrativo", "administrador", "tecnico em administracao", "area administrativa",
         "analista tecnico-administrativo", "assistente tecnico-administrativo"],
    ),
}


def criar(apps, schema_editor):
    Banca = apps.get_model("catalogo", "Banca")
    AreaAtuacao = apps.get_model("catalogo", "AreaAtuacao")
    RegraArea = apps.get_model("catalogo", "RegraArea")

    for nome, slug, site, apelidos in BANCAS:
        Banca.objects.update_or_create(slug=slug, defaults={"nome": nome, "site": site, "apelidos": apelidos})

    for nome, (descricao, termos_orgao, termos_cargo) in AREAS.items():
        area, _ = AreaAtuacao.objects.update_or_create(
            slug=slugify(nome), defaults={"nome": nome, "descricao": descricao}
        )
        for termo in termos_orgao:
            RegraArea.objects.get_or_create(termo=termo, alvo="orgao", area=area)
        for termo in termos_cargo:
            RegraArea.objects.get_or_create(termo=termo, alvo="cargo", area=area)


class Migration(migrations.Migration):
    dependencies = [("catalogo", "0002_initial")]
    operations = [migrations.RunPython(criar, migrations.RunPython.noop)]
