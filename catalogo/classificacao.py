"""Classificação por área de atuação, a partir das RegraArea.

- Regra com alvo "cargo" procura o termo no nome do cargo.
- Regra com alvo "orgao" procura o termo no título do concurso e no nome do órgão.
O termo casa como palavra inteira ("tre" não casa com "entre"); termine com "*"
para casar prefixo ("professor*" casa "professora", "professores").

Cargo: recebe as áreas das regras de cargo e de órgão (um analista de TI de um
tribunal é Tribunais + TI). Concurso: recebe as áreas das regras aplicadas ao
título/órgão mais a união das áreas dos cargos — assim concursos sem cargos detalhados (como os da
FGV) também aparecem no filtro. Itens com areas_manuais=True não são tocados.
"""
import re
from functools import lru_cache

from ingestao.texto import normalizar

from .models import Cargo, Concurso, RegraArea


@lru_cache(maxsize=2048)
def _padrao(termo_normalizado: str) -> re.Pattern:
    prefixo = termo_normalizado.endswith("*")
    nucleo = re.escape(termo_normalizado.rstrip("*"))
    return re.compile(rf"\b{nucleo}" + ("" if prefixo else r"\b"))


def regras_ativas():
    return [
        (normalizar(regra.termo), regra.alvo, regra.area_id)
        for regra in RegraArea.objects.filter(ativa=True).only("termo", "alvo", "area_id")
    ]


def areas_para(texto_cargo: str, texto_orgao: str, regras=None, alvos=("cargo", "orgao")) -> set[int]:
    regras = regras_ativas() if regras is None else regras
    textos = {"cargo": normalizar(texto_cargo), "orgao": normalizar(texto_orgao)}
    encontradas = set()
    for termo, alvo, area_id in regras:
        if alvo not in alvos or not termo or not textos[alvo]:
            continue
        if _padrao(termo).search(textos[alvo]):
            encontradas.add(area_id)
    return encontradas


def _contexto_orgao(concurso: Concurso) -> str:
    partes = [concurso.titulo]
    if concurso.orgao_id:
        partes += [concurso.orgao.nome, concurso.orgao.sigla]
    return " ".join(filter(None, partes))


def classificar_cargo(cargo: Cargo, regras=None) -> bool:
    """Aplica as regras ao cargo. Devolve True se as áreas mudaram."""
    if cargo.areas_manuais:
        return False
    novas = areas_para(cargo.nome, _contexto_orgao(cargo.concurso), regras)
    atuais = set(cargo.areas.values_list("id", flat=True))
    if novas == atuais:
        return False
    cargo.areas.set(novas)
    return True


def classificar_concurso(concurso: Concurso, regras=None, incluir_cargos: bool = True) -> bool:
    if concurso.areas_manuais:
        return False
    regras = regras_ativas() if regras is None else regras
    if incluir_cargos:
        for cargo in concurso.cargos.all():
            classificar_cargo(cargo, regras)
    # Títulos costumam trazer o cargo ("SEDF 26 PROFESSOR"): regras de cargo valem no título também.
    novas = areas_para(concurso.titulo, _contexto_orgao(concurso), regras)
    novas |= set(Cargo.areas.through.objects.filter(cargo__concurso=concurso).values_list("areaatuacao_id", flat=True))
    atuais = set(concurso.areas.values_list("id", flat=True))
    if novas == atuais:
        return False
    concurso.areas.set(novas)
    return True


def reclassificar_todos() -> int:
    regras = regras_ativas()
    alterados = 0
    for concurso in Concurso.objects.select_related("orgao").prefetch_related("cargos"):
        alterados += classificar_concurso(concurso, regras)
    return alterados
