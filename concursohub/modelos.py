"""Vocabulário comum: situação do concurso, esfera e tipo de documento.

Os valores são os que vão para o JSON do site; os rótulos ficam no site.
"""
from enum import StrEnum


class Situacao(StrEnum):
    PREVISTO = "previsto"
    ABERTO = "aberto"  # inscrições abertas
    ANDAMENTO = "andamento"
    ENCERRADO = "encerrado"


class Esfera(StrEnum):
    FEDERAL = "federal"
    ESTADUAL = "estadual"
    DISTRITAL = "distrital"
    MUNICIPAL = "municipal"


class TipoDocumento(StrEnum):
    EDITAL_ABERTURA = "edital_abertura"
    RETIFICACAO = "retificacao"
    COMUNICADO = "comunicado"
    INSCRITOS = "inscritos"
    GABARITO = "gabarito"
    RESULTADO = "resultado"
    CONVOCACAO = "convocacao"
    HOMOLOGACAO = "homologacao"
    PRORROGACAO = "prorrogacao"
    OUTRO = "outro"
