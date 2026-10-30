"""Palpites a partir do título, usados só enquanto o órgão não foi vinculado.

Bancas costumam nomear concursos com siglas ("TJ CE 25", "CGU 26 AFFC",
"Prefeitura de Macaé"). As regras abaixo acertam a maioria; o que errar você
corrige no admin, e a correção prevalece.
"""
import re

from ingestao.texto import normalizar

from .models import Esfera

_UFS = "ac al ap am ba ce df es go ma mt ms mg pa pb pr pe pi rj rn rs ro rr sc sp se to".split()
_UF = r"(?:" + "|".join(_UFS) + r")"

_REGRAS = [
    (Esfera.MUNICIPAL, r"\bprefeitura\b|\bmunicipio\b|\bmunicipal\b|\bcamara municipal\b|\bcamara de vereadores\b"),
    (Esfera.DISTRITAL, r"\bdistrito federal\b|\bgdf\b|\b(?:tjdft|pcdf|pmdf|cbmdf|cldf|tcdf|sedf|seec df)\b|\b\w+ df\b|\bdf \d{2}\b"),
    (
        Esfera.FEDERAL,
        r"\bfederal\b|\buniao\b|\bministerio d[aoe]s?\b|\bcnu\d?\b|\bcpnu\d?\b|\bnacional\b"
        r"|\b(?:trf|trt|tre|tst|stj|stf|tse|stm|tcu|cgu|agu|pgfn|pf|prf|inss|ibge|ibama|anvisa|anac|anatel|aneel|anp|ans|antt|bacen|bcb|cvm|susep|receita|mre|irbr|abin|dpu|mpu|mpf|mpt|cnmp|cnj|camara dos deputados|senado|cd|ebserh|petrobras|caixa|banco do brasil|bnb|bnds|bndes|correios|serpro|dataprev|capes|cnpq|inb|abdi|agsus)\b",
    ),
    (
        Esfera.ESTADUAL,
        r"\bestado\b|\bestadual\b|\bassembleia legislativa\b"
        rf"|\b(?:tj|tce|mp|pc|pm|cbm|dpe|pge|sefaz|seduc|sesa|sejus|detran|ale|al) ?{_UF}\b"
        rf"|\b(?:tj|tce|mp|pc|pm|dpe|pge|sefaz|seduc|detran){_UF}\b"
        # Padrão Cebraspe "SIGLA UF AA" (ex.: "AGEPAR PR 26"); federais já casaram acima.
        rf"|^[a-z]+ {_UF} \d{{2}}\b",
    ),
]
_REGRAS_COMPILADAS = [(esfera, re.compile(padrao)) for esfera, padrao in _REGRAS]


def inferir_esfera(titulo: str) -> str:
    texto = normalizar(titulo)
    for esfera, padrao in _REGRAS_COMPILADAS:
        if padrao.search(texto):
            return esfera
    return ""
