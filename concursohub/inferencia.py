"""Esfera (federal, estadual, distrital, municipal) inferida do título.

Bancas costumam nomear concursos com siglas ("TJ CE 25", "CGU 26 AFFC",
"Prefeitura de Macaé"). As regras abaixo acertam a maioria; quando errarem,
adicione o caso em tests/test_classificacao.py e ajuste a regra.
"""
import re

from .modelos import Esfera
from .texto import normalizar

_UFS = "ac al ap am ba ce df es go ma mt ms mg pa pb pr pe pi rj rn rs ro rr sc sp se to".split()
_UF = r"(?:" + "|".join(_UFS) + r")"
# "Pará" só com artigo, para não confundir com a preposição "para".
_ESTADOS = (
    r"(?:acre|alagoas|amapa|amazonas|bahia|ceara|espirito santo|goias|maranhao|mato grosso(?: do sul)?"
    r"|minas gerais|d[oe] para|paraiba|parana|pernambuco|piaui|rio de janeiro|rio grande do (?:norte|sul)"
    r"|rondonia|roraima|santa catarina|sao paulo|sergipe|tocantins)"
)

_REGRAS = [
    (Esfera.MUNICIPAL, r"\bprefeitura\b|\bpref\b|\bmunicipio\b|\bmunicipal\b|\bcamara municipal\b|\bcamara de vereadores\b"),
    (Esfera.DISTRITAL, r"\bdistrito federal\b|\bgdf\b|\b(?:tjdft|pcdf|pmdf|cbmdf|cldf|tcdf|sedf|seec df)\b|\b\w+ df\b|\bdf \d{2}\b"),
    (
        Esfera.FEDERAL,
        r"\bfederal\b|\buniao\b|\bministerio d[aoe]s?\b|\bcnu\d?\b|\bcpnu\d?\b|\bnacional\b"
        r"|\b(?:trf|trt|tre|tst|stj|stf|tse|stm|tcu|cgu|agu|pgfn|pf|prf|inss|ibge|ibama|anvisa|anac|anatel|aneel|anp|ans|antt|bacen|bcb|cvm|susep|receita|mre|irbr|abin|dpu|mpu|mpf|mpt|cnmp|cnj|camara dos deputados|senado|cd|ebserh|petrobras|caixa|banco do brasil|bnb|bnds|bndes|correios|serpro|dataprev|capes|cnpq|inb|abdi|agsus|antaq|ancine|anm|funpresp|drei|amazul|cprm|nav brasil)\b",
    ),
    (
        Esfera.ESTADUAL,
        r"\bestado\b|\bestadual\b|\bassembleia legislativa\b"
        rf"|\b(?:tj|tce|mp|pc|pm|cbm|dpe|pge|sefaz|seduc|sesa|sejus|sead|seplag|seap|detran|ale|al)[ /-]?{_UF}\b"
        # Padrão Cebraspe "SIGLA UF AA" (ex.: "AGEPAR PR 26"); federais já casaram acima.
        rf"|^[a-z]+ {_UF} \d{{2}}\b"
        # Nome do estado por extenso; prefeituras e órgãos federais já casaram acima.
        rf"|\b{_ESTADOS}\b",
    ),
]
_REGRAS_COMPILADAS = [(esfera, re.compile(padrao)) for esfera, padrao in _REGRAS]


def inferir_esfera(titulo: str) -> str:
    texto = normalizar(titulo)
    for esfera, padrao in _REGRAS_COMPILADAS:
        if padrao.search(texto):
            return esfera
    return ""
