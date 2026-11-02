"""Áreas de atuação por regras de palavras.

Cada área tem termos de órgão, procurados no título do concurso, e termos de
cargo, procurados no nome de cada cargo e também no título (que costuma trazer
o cargo: "SEDF 26 PROFESSOR"). Os termos casam como palavra inteira, sem
acentos nem maiúsculas ("tre" não casa com "entre"); "*" no fim casa prefixo
("professor*" casa "professora").

As áreas são independentes: um "Analista de TI de tribunal" entra em Tribunais e em TI.
Classificação errada: adicione o caso em tests/test_classificacao.py antes de mexer aqui.
"""
import re

from .texto import normalizar

# área: (termos de órgão, termos de cargo)
AREAS = {
    "Tribunais": (
        ["tribunal de justica", "tribunal regional", "tribunal superior", "supremo tribunal", "justica federal",
         "justica do trabalho", "justica eleitoral", "justica militar",
         "tj", "tjdft", "trf", "trt", "tre", "tse", "tst", "stj", "stf", "stm", "cnj"],
        ["analista judiciario", "tecnico judiciario", "oficial de justica", "juiz*"],
    ),
    "Fiscal": (
        ["receita federal", "secretaria da fazenda", "secretaria de fazenda", "sefaz*", "fazenda estadual",
         "fazenda municipal", "secretaria de estado da fazenda", "secretaria de estado de fazenda",
         "secretaria municipal de fazenda"],
        ["auditor-fiscal", "auditor fiscal", "fiscal de tributos", "fiscal de rendas", "fiscal tributario",
         "auditor de tributos", "analista tributario", "agente fiscal"],
    ),
    "Controle": (
        ["tribunal de contas", "tcu", "tce", "tcm", "tcdf", "cgu", "controladoria*", "auditoria-geral", "auditoria geral"],
        ["auditor federal de financas e controle", "auditor de controle externo", "analista de controle*",
         "auditor de controle interno", "affc"],
    ),
    "Policial": (
        ["policia*", "pf", "prf", "pc", "pm", "pcdf", "pmdf", "cbm", "cbmdf", "corpo de bombeiros", "policia penal", "depen",
         "guarda municipal", "seguranca municipal", "administracao penitenciaria"],
        ["delegado*", "agente de policia", "escrivao", "perito criminal", "papiloscopista", "investigador*",
         "soldado", "policial*", "agente penitenciario", "policia penal"],
    ),
    "Bancária": (
        ["banco do brasil", "caixa economica", "caixa", "bnb", "banco do nordeste", "bndes", "banco central",
         "bacen", "bcb", "basa", "banco da amazonia", "banrisul", "brb", "banestes"],
        ["escriturario", "tecnico bancario"],
    ),
    "Legislativo": (
        ["camara dos deputados", "senado", "assembleia legislativa", "camara municipal", "camara legislativa", "cldf", "cd"],
        ["analista legislativo", "consultor legislativo", "tecnico legislativo"],
    ),
    "Jurídica": (
        ["advocacia-geral da uniao", "agu", "pgfn", "pge", "pgm", "procuradoria*", "defensoria*", "dpu", "dpe",
         "ministerio publico", "mpu", "mpf", "mpt", "mpm"],
        ["procurador*", "advogado*", "defensor*", "promotor*", "analista juridico", "assessor juridico"],
    ),
    "Regulação": (
        ["agencia nacional", "anvisa", "anac", "anatel", "aneel", "anp", "ans", "antt", "antaq", "ana", "ancine", "anm",
         "agencia reguladora*"],
        ["especialista em regulacao", "analista em regulacao", "tecnico em regulacao"],
    ),
    "TI": (
        [],
        ["tecnologia da informacao", "ti", "desenvolvimento de sistemas", "ciencia de dados", "banco de dados",
         "infraestrutura de ti", "seguranca da informacao", "analista de sistemas", "programador*", "informatica",
         "suporte tecnico", "governanca de ti", "inteligencia artificial", "engenharia de software",
         "analise de dados", "cientista de dados"],
    ),
    "Saúde": (
        ["ebserh", "secretaria de saude", "secretaria da saude", "hospital*", "fundacao hospitalar",
         "secretaria de estado da saude", "secretaria de estado de saude", "secretaria municipal de saude"],
        ["medico*", "enfermeiro*", "enfermagem", "farmaceutico*", "odontolog*", "dentista", "fisioterapeut*",
         "nutricionista", "psicolog*", "fonoaudiolog*", "biomedic*", "terapeuta ocupacional", "assistente social"],
    ),
    "Educação": (
        ["seduc", "sedf", "seec", "secretaria de educacao", "secretaria da educacao", "universidade*", "instituto federal",
         "colegio pedro ii", "secretaria de estado da educacao", "secretaria de estado de educacao",
         "secretaria municipal de educacao"],
        ["professor*", "pedagog*", "docente", "magisterio", "orientador educacional", "supervisor escolar"],
    ),
    "Administrativa": (
        [],
        ["assistente administrativo", "auxiliar administrativo", "agente administrativo", "analista administrativo",
         "tecnico administrativo", "administrador", "tecnico em administracao", "area administrativa",
         "analista tecnico-administrativo", "assistente tecnico-administrativo"],
    ),
}


def _padrao(termo: str) -> re.Pattern:
    termo = normalizar(termo)
    prefixo = termo.endswith("*")
    nucleo = re.escape(termo.rstrip("*"))
    return re.compile(rf"\b{nucleo}" + ("" if prefixo else r"\b"))


_COMPILADAS = {
    area: ([_padrao(t) for t in orgao], [_padrao(t) for t in cargo]) for area, (orgao, cargo) in AREAS.items()
}


def areas_do_concurso(titulo: str, cargos: list[str] = ()) -> list[str]:
    """Áreas do concurso, em ordem alfabética, pelo título e pelos nomes dos cargos."""
    titulo = normalizar(titulo)
    cargos = [normalizar(c) for c in cargos if c]
    encontradas = set()
    for area, (orgao, cargo) in _COMPILADAS.items():
        if any(p.search(titulo) for p in orgao + cargo) or any(p.search(c) for p in cargo for c in cargos):
            encontradas.add(area)
    return sorted(encontradas)
