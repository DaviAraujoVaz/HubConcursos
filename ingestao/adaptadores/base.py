"""Interface comum dos adaptadores de fonte.

Cada fonte (DOU, Cebraspe, FGV…) é uma classe que sabe:
  1. coletar(): devolver o que encontrou, já estruturado, em objetos simples
     (ConcursoExtraido / DocumentoExtraido), sem tocar no banco;
  2. baixar_arquivo(): trazer o conteúdo de um documento.

Gravar no banco, deduplicar e emitir eventos é responsabilidade de
ingestao.persistencia — igual para todas as fontes. Adicionar uma banca nova é
escrever uma classe destas e registrá-la em REGISTRO.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Iterator


@dataclass
class DocumentoExtraido:
    chave_externa: str
    titulo: str
    url: str = ""
    tipo: str = "outro"
    publicado_em: datetime | None = None
    extensao: str = "pdf"
    texto: str = ""
    conteudo: bytes | None = None  # quando o adaptador já tem o arquivo (ex.: XML do DOU)
    metadados: dict = field(default_factory=dict)


@dataclass
class CargoExtraido:
    nome: str
    codigo_externo: str = ""
    remuneracao: Decimal | None = None
    vagas: int | None = None


@dataclass
class ConcursoExtraido:
    chave_externa: str
    titulo: str
    banca_slug: str = ""
    url_oficial: str = ""
    ano: int | None = None
    situacao: str = "previsto"
    maturidade: str = "5_edital"
    inscricoes_inicio: datetime | None = None
    inscricoes_fim: datetime | None = None
    vagas_total: int | None = None
    remuneracao_maxima: Decimal | None = None
    cargos: list[CargoExtraido] = field(default_factory=list)
    documentos: list[DocumentoExtraido] = field(default_factory=list)
    atributos: dict = field(default_factory=dict)
    bruto: bytes | None = None  # resposta original da fonte, guardada para reprocessar
    bruto_extensao: str = "json"


@dataclass
class ResultadoColeta:
    concursos: list[ConcursoExtraido] = field(default_factory=list)
    # Documentos que ainda não têm concurso conhecido (ex.: atos do DOU).
    documentos_soltos: list[DocumentoExtraido] = field(default_factory=list)


class Adaptador:
    slug: str = ""
    nome: str = ""

    def __init__(self, cliente=None):
        from ..http import ClienteHttp

        self.cliente = cliente or ClienteHttp()

    def coletar(self, **opcoes) -> Iterator[ResultadoColeta]:
        """Gera resultados aos poucos (um por concurso, por dia de DOU…),
        para que uma falha no meio não perca o que já foi coletado."""
        raise NotImplementedError

    def baixar_arquivo(self, documento: DocumentoExtraido) -> bytes | None:
        if documento.conteudo is not None:
            return documento.conteudo
        if not documento.url:
            return None
        return self.cliente.get(documento.url).content


REGISTRO: dict[str, type[Adaptador]] = {}


def registrar(classe: type[Adaptador]) -> type[Adaptador]:
    REGISTRO[classe.slug] = classe
    return classe


def adaptadores_registrados() -> Iterable[str]:
    return sorted(REGISTRO)
