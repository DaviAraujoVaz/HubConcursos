"""Interface comum dos adaptadores de fonte.

Cada fonte (Cebraspe, FGV…) é uma classe cujo coletar() devolve os concursos
encontrados em objetos simples (ConcursoExtraido / DocumentoExtraido). O
adaptador não classifica nem grava nada: isso é de concursohub.coletar, igual
para todas as fontes. Adicionar uma banca nova é escrever uma classe destas e
registrá-la com @registrar.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Iterator


@dataclass
class DocumentoExtraido:
    titulo: str
    url: str = ""
    tipo: str = "outro"
    publicado_em: datetime | None = None


@dataclass
class CargoExtraido:
    nome: str
    codigo_externo: str = ""


@dataclass
class ConcursoExtraido:
    chave_externa: str
    titulo: str
    banca_slug: str = ""
    url_oficial: str = ""
    ano: int | None = None
    situacao: str = "previsto"
    inscricoes_inicio: datetime | None = None
    inscricoes_fim: datetime | None = None
    vagas_total: int | None = None
    remuneracao_maxima: Decimal | None = None
    cargos: list[CargoExtraido] = field(default_factory=list)
    documentos: list[DocumentoExtraido] = field(default_factory=list)


class Adaptador:
    slug: str = ""
    nome: str = ""

    def __init__(self, cliente=None):
        from ..http import ClienteHttp

        self.cliente = cliente or ClienteHttp()

    def coletar(self, **opcoes) -> Iterator[ConcursoExtraido]:
        raise NotImplementedError


REGISTRO: dict[str, type[Adaptador]] = {}


def registrar(classe: type[Adaptador]) -> type[Adaptador]:
    REGISTRO[classe.slug] = classe
    return classe


def adaptadores_registrados() -> Iterable[str]:
    return sorted(REGISTRO)
