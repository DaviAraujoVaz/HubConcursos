"""Áreas de atuação por regras de palavras.

Cada área tem termos de órgão, procurados no título do concurso, e termos de
cargo, procurados no nome de cada cargo e também no título (que costuma trazer
o cargo: "SEDF 26 PROFESSOR"). Os termos casam como palavra inteira, sem
acentos nem maiúsculas ("tre" não casa com "entre"); "*" no fim casa prefixo
("professor*" casa "professora"). "exceto" lista expressões que anulam a área
("engenharia de software" é TI, não Engenharia).

Há dois tipos de área, e um concurso pode ter vários de cada:
- carreira/órgão: Tribunais, Controle, Policial, Fiscal… (onde se trabalha);
- formação/atuação: TI, Engenharia, Saúde, Contabilidade… (o que se faz).
Um "Analista de TI de tribunal" entra em Tribunais e em TI.

Cargo com perfil ou especialidade ("ANALISTA DE TECNOLOGIA DA INFORMAÇÃO –
PERFIL: ADVOCACIA") é classificado pelo perfil: é vaga de advogado, não de TI.
Classificação errada: adicione o caso em tests/test_classificacao.py antes de mexer aqui.
"""
import re

from .texto import normalizar

AREAS = {
    "Tribunais": {
        "orgao": ["tribunal de justica", "tribunal regional", "tribunal superior", "supremo tribunal", "justica federal",
                  "justica do trabalho", "justica eleitoral", "justica militar",
                  "tj", "tjdft", "trf", "trt", "tre", "tse", "tst", "stj", "stf", "stm", "cnj"],
        "cargo": ["analista judiciario", "tecnico judiciario", "oficial de justica", "juiz*"],
    },
    "Fiscal": {
        "orgao": ["receita federal", "secretaria da fazenda", "secretaria de fazenda", "sefaz*", "fazenda estadual",
                  "fazenda municipal", "secretaria de estado da fazenda", "secretaria de estado de fazenda",
                  "secretaria municipal de fazenda"],
        "cargo": ["auditor-fiscal", "auditor fiscal", "fiscal de tributos", "fiscal de rendas", "fiscal tributario",
                  "auditor de tributos", "analista tributario", "agente fiscal"],
    },
    "Controle": {
        "orgao": ["tribunal de contas", "tcu", "tce", "tcm", "tcdf", "cgu", "controladoria*", "auditoria-geral",
                  "auditoria geral"],
        "cargo": ["auditor federal de financas e controle", "auditor de controle externo", "analista de controle*",
                  "auditor de controle interno", "auditor municipal de controle interno", "affc"],
    },
    "Policial": {
        "orgao": ["policia*", "pf", "prf", "pc", "pm", "pcdf", "pmdf", "cbm", "cbmdf", "corpo de bombeiros",
                  "policia penal", "depen", "guarda municipal", "seguranca municipal", "administracao penitenciaria"],
        "cargo": ["delegado*", "agente de policia", "escrivao", "perito criminal", "papiloscopista", "investigador*",
                  "soldado", "policial*", "agente penitenciario", "policia penal", "datiloscopista", "medico-legista"],
    },
    "Bancária": {
        "orgao": ["banco do brasil", "caixa economica", "caixa", "bnb", "banco do nordeste", "bndes", "banco central",
                  "bacen", "bcb", "basa", "banco da amazonia", "banrisul", "brb", "banestes"],
        "cargo": ["escriturario", "tecnico bancario"],
    },
    "Legislativo": {
        "orgao": ["camara dos deputados", "senado", "assembleia legislativa", "camara municipal", "camara legislativa",
                  "cldf", "cd"],
        "cargo": ["analista legislativo", "consultor legislativo", "tecnico legislativo"],
    },
    "Jurídica": {
        "orgao": ["advocacia-geral da uniao", "agu", "pgfn", "pge", "pgm", "procuradoria*", "defensoria*", "dpu", "dpe",
                  "ministerio publico", "mpu", "mpf", "mpt", "mpm"],
        "cargo": ["procurador*", "advogado*", "advocacia", "defensor", "defensora", "defensores", "promotor*", "juridic*", "direito"],
    },
    "Regulação": {
        "orgao": ["agencia nacional", "anvisa", "anac", "anatel", "aneel", "anp", "ans", "antt", "antaq", "ana",
                  "ancine", "anm", "agencia reguladora*"],
        "cargo": ["especialista em regulacao", "analista em regulacao", "tecnico em regulacao"],
    },
    "TI": {
        "orgao": ["dataprev", "serpro", "empresa de tecnologia*"],
        "cargo": ["tecnologia da informacao", "ti", "tic", "desenvolvimento de sistemas", "desenvolvimento de software",
                  "engenharia de software", "software", "ciencia de dados", "banco de dados", "analise de dados",
                  "cientista de dados", "inteligencia artificial", "inteligencia da informacao", "infraestrutura de ti",
                  "seguranca da informacao", "seguranca cibernetica", "analista de sistema*", "sistemas de informacao",
                  "programador*", "informatica", "suporte tecnico", "analista de suporte", "governanca de ti",
                  "redes de comunicacao", "analista de redes", "tecnico de rede*", "computador*", "processamento",
                  "sustentacao tecnologica"],
    },
    "Engenharia": {
        "orgao": [],
        "cargo": ["engenheiro*", "engenharia*"],
        "exceto": ["engenharia de software", "engenharia de dados", "engenharia e sustentacao tecnologica"],
    },
    "Contabilidade e Economia": {
        "orgao": [],
        "cargo": ["contador", "contadora", "contadores", "contabil*", "contabeis", "economista", "economia", "economico-financeir*",
                  "economico financeir*", "estatistic*", "atuari*"],
    },
    "Comunicação": {
        "orgao": [],
        "cargo": ["comunicacao social", "jornalis*", "relacoes publicas", "publicidade", "design grafico", "designer*",
                  "audiovisual", "audio visual", "radialista", "cinegrafista", "fotograf*", "redator*"],
    },
    "Saúde": {
        "orgao": ["ebserh", "secretaria de saude", "secretaria da saude", "hospital*", "fundacao hospitalar",
                  "secretaria de estado da saude", "secretaria de estado de saude", "secretaria municipal de saude"],
        "cargo": ["medico*", "enfermeiro*", "enfermagem", "farmaceutico*", "odontolog*", "dentista", "fisioterapeut*",
                  "nutricionista", "psicolog*", "fonoaudiolog*", "biomedic*", "terapeuta ocupacional",
                  "assistente social", "assistencia social", "veterinari*"],
    },
    "Educação": {
        "orgao": ["seduc", "sedf", "seec", "secretaria de educacao", "secretaria da educacao", "universidade*",
                  "instituto federal", "colegio pedro ii", "secretaria de estado da educacao",
                  "secretaria de estado de educacao", "secretaria municipal de educacao"],
        "cargo": ["professor*", "pedagog*", "docente", "magisterio", "orientador educacional", "supervisor escolar",
                  "tecnico em educacao"],
    },
    "Administrativa": {
        "orgao": [],
        "cargo": ["assistente administrativo", "auxiliar administrativo", "agente administrativo", "analista administrativo",
                  "tecnico administrativo", "administrador*", "tecnico em administracao", "analista em administracao",
                  "area administrativa", "administracao e governanca", "analista tecnico-administrativo",
                  "assistente tecnico-administrativo"],
    },
}

# Áreas de carreira/órgão: num cargo com perfil, valem junto com as do perfil
# (AFFC – especialidade TI é Controle e TI). As demais são substituídas pelo perfil.
CARREIRAS = {"Tribunais", "Fiscal", "Controle", "Policial", "Bancária", "Legislativo", "Regulação"}


def _padrao(termo: str) -> re.Pattern:
    termo = normalizar(termo)
    prefixo = termo.endswith("*")
    nucleo = re.escape(termo.rstrip("*"))
    return re.compile(rf"\b{nucleo}" + ("" if prefixo else r"\b"))


_COMPILADAS = {
    area: (
        [_padrao(t) for t in regras["orgao"]],
        [_padrao(t) for t in regras["cargo"]],
        [_padrao(t) for t in regras.get("exceto", [])],
    )
    for area, regras in AREAS.items()
}
# "ANALISTA – PERFIL: ADVOCACIA", "AUDITOR – ÁREA: DIREITO", "TÉCNICO – FUNÇÃO: JORNALISTA"
_QUALIFICADOR = re.compile(r"\b(?:perfil|especialidade|area|funcao)\b\s*[:\-–]?\s*")


def _casa(texto: str, padroes, exceto) -> bool:
    return any(p.search(texto) for p in padroes) and not any(e.search(texto) for e in exceto)


def _areas_de_cargo(texto: str) -> set[str]:
    return {area for area, (_, cargo, exceto) in _COMPILADAS.items() if _casa(texto, cargo, exceto)}


def areas_do_cargo(nome: str) -> list[str]:
    """Áreas de um cargo. Com perfil/especialidade, o perfil decide (mais as carreiras do nome)."""
    texto = normalizar(nome)
    todas = _areas_de_cargo(texto)
    qualificador = _QUALIFICADOR.search(texto)
    if qualificador:
        do_perfil = _areas_de_cargo(texto[qualificador.end():])
        if do_perfil:
            todas = do_perfil | (todas & CARREIRAS)
    return sorted(todas)


def areas_do_titulo(titulo: str) -> list[str]:
    texto = normalizar(titulo)
    return sorted(
        area for area, (orgao, cargo, exceto) in _COMPILADAS.items() if _casa(texto, orgao + cargo, exceto)
    )


def areas_do_concurso(titulo: str, cargos: list[str] = ()) -> list[str]:
    """Áreas do concurso, em ordem alfabética: as do título mais as de cada cargo."""
    encontradas = set(areas_do_titulo(titulo))
    for cargo in cargos:
        encontradas.update(areas_do_cargo(cargo))
    return sorted(encontradas)
