"""Coleta as fontes e gera os dados que o site lê.

    python -m concursohub.coletar               # todas as fontes
    python -m concursohub.coletar cebraspe      # só uma (as outras ficam como estavam)
    python -m concursohub.coletar --sem-editais # não baixa editais novos (mais rápido)

Gera dois arquivos em site/dados/:
- concursos.json: os concursos ativos, já com esfera, áreas, cargos (com
  remuneração, quando o edital informa) e tipo de cada documento. Fica no Git e
  só é reescrito quando algo muda, então o histórico do repositório mostra o
  que mudou em cada coleta.
- status.json: quando a coleta rodou e como foi cada fonte. Não vai para o Git.

Os cargos e salários vêm do edital de abertura em PDF (ver edital.py). Cada
edital é lido uma vez só: o resultado fica em cache/editais.json, no Git, pela
URL do PDF (um edital retificado ganha URL nova).

Se uma fonte falhar, os concursos dela da coleta anterior são mantidos, para o
site não esvaziar por causa de um site fora do ar. O comando termina com erro
(código 1), o que faz o GitHub Actions avisar por e-mail.
"""
import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from . import edital
from .adaptadores import REGISTRO
from .areas import areas_do_cargo, areas_do_titulo
from .classificador import classificar_tipo
from .inferencia import inferir_esfera
from .texto import FUSO_BR

log = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "site" / "dados"
CACHE_EDITAIS = RAIZ / "cache" / "editais.json"
# Documentos mais recentes guardados por concurso; o resto fica na página oficial.
MAX_DOCUMENTOS = 15
# Edital que falhou (fora do ar, PDF quebrado) é tentado de novo depois disso.
NOVA_TENTATIVA = timedelta(days=7)
_MUITO_ANTIGO = datetime.min.replace(tzinfo=FUSO_BR)


def _iso(valor: datetime | None) -> str | None:
    return valor.astimezone(FUSO_BR).isoformat(timespec="minutes") if valor else None


def _float(valor) -> float | None:
    return float(valor) if valor else None


def tipo_do_documento(documento) -> str:
    """O tipo que a fonte informou (ex.: gabaritos da Cebraspe) ou, na falta, o das regras pelo título."""
    return str(documento.tipo if documento.tipo != "outro" else classificar_tipo(documento.titulo))


# --- Edital: cache, download e leitura ------------------------------------------

def ler_edital(concurso, cliente, cache: dict, agora: datetime, baixar: bool = True) -> dict | None:
    """Resultado da leitura do edital do concurso (do cache ou baixando o PDF)."""
    doc = edital.escolher_edital(concurso.documentos, tipo_do_documento)
    if doc is None:
        return None
    guardado = cache.get(doc.url)
    if guardado and guardado.get("versao") == edital.VERSAO:
        tentar_de_novo = guardado.get("erro") and agora - datetime.fromisoformat(guardado["lido_em"]) > NOVA_TENTATIVA
        if not tentar_de_novo:
            return guardado
    if not baixar:
        return guardado
    resultado = {"versao": edital.VERSAO, "lido_em": _iso(agora), "cargos": [], "remuneracao_unica": None, "erro": ""}
    try:
        texto = edital.texto_do_pdf(cliente.get(doc.url).content)
        resultado["cargos"] = [
            {"nome": c.nome, "remuneracao": str(c.remuneracao) if c.remuneracao else None, "numero": c.numero}
            for c in edital.analisar(texto)
        ]
        unica = edital.remuneracao_unica(texto)
        resultado["remuneracao_unica"] = str(unica) if unica else None
    except Exception as erro:  # um edital com problema não derruba a coleta
        log.warning("Não foi possível ler o edital %s: %s", doc.url, erro)
        resultado["erro"] = f"{type(erro).__name__}: {erro}"[:300]
    cache[doc.url] = resultado
    return resultado


def _numero(codigo: str) -> int | None:
    digitos = "".join(c for c in codigo or "" if c.isdigit())
    return int(digitos) if digitos else None


def montar_cargos(concurso, leitura: dict | None) -> list[dict]:
    """Cargos com remuneração e áreas. Nomes da fonte quando ela informa (Cebraspe);
    senão, os do edital (FGV). A remuneração sempre vem do edital."""
    do_edital = (leitura or {}).get("cargos") or []
    unica = (leitura or {}).get("remuneracao_unica")
    if concurso.cargos:
        por_numero = {c["numero"]: c["remuneracao"] for c in do_edital if c.get("numero")}
        por_ordem = [c["remuneracao"] for c in do_edital] if len(do_edital) == len(concurso.cargos) else []
        cargos = []
        for i, cargo in enumerate(concurso.cargos):
            valor = por_numero.get(_numero(cargo.codigo_externo)) if por_numero else None
            if valor is None and por_ordem:
                valor = por_ordem[i]
            if valor is None and not do_edital:
                valor = unica
            cargos.append((cargo.nome, valor))
    else:
        cargos = [(c["nome"], c["remuneracao"]) for c in do_edital]
    return [{"nome": nome, "remuneracao": _float(valor), "areas": areas_do_cargo(nome)} for nome, valor in cargos]


# --- Concurso → JSON ------------------------------------------------------------

def para_dict(concurso, primeiro_visto: str | None, leitura: dict | None = None) -> dict:
    documentos = sorted(concurso.documentos, key=lambda d: d.publicado_em or _MUITO_ANTIGO, reverse=True)
    cargos = montar_cargos(concurso, leitura)
    areas = set(areas_do_titulo(concurso.titulo))
    for cargo in cargos:
        areas.update(cargo["areas"])
    salarios = [Decimal(str(c["remuneracao"])) for c in cargos if c["remuneracao"]]
    if concurso.remuneracao_maxima:
        salarios.append(concurso.remuneracao_maxima)
    if not salarios and leitura and leitura.get("remuneracao_unica"):
        salarios.append(Decimal(leitura["remuneracao_unica"]))
    return {
        "id": concurso.chave_externa,
        "titulo": concurso.titulo,
        "banca": concurso.banca_slug,
        "situacao": str(concurso.situacao),
        "esfera": str(inferir_esfera(concurso.titulo)),
        "areas": sorted(areas),
        "url": concurso.url_oficial,
        "ano": concurso.ano,
        "inscricoes_inicio": _iso(concurso.inscricoes_inicio),
        "inscricoes_fim": _iso(concurso.inscricoes_fim),
        "vagas": concurso.vagas_total,
        "remuneracao_maxima": _float(max(salarios)) if salarios else None,
        "cargos": cargos,
        "documentos": [
            {
                "titulo": d.titulo,
                "tipo": tipo_do_documento(d),
                "url": d.url,
                "data": d.publicado_em.astimezone(FUSO_BR).date().isoformat() if d.publicado_em else None,
            }
            for d in documentos[:MAX_DOCUMENTOS]
        ],
        "total_documentos": len(documentos),
        "ultima_publicacao": _iso(documentos[0].publicado_em) if documentos else None,
        # Data em que o ConcursoHub viu o concurso pela primeira vez. Vazio para o
        # que já existia na primeira coleta da fonte, que não é novidade.
        "primeiro_visto": primeiro_visto,
    }


def _ler(caminho: Path) -> dict:
    if not caminho.exists():
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))


def _gravar(caminho: Path, dados: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=1, sort_keys=False) + "\n", encoding="utf-8")


def gerar(
    fontes: list[str],
    saida: Path = SAIDA,
    clientes: dict | None = None,
    agora: datetime | None = None,
    cache_editais: Path = CACHE_EDITAIS,
    baixar_editais: bool = True,
) -> dict:
    """Coleta `fontes`, atualiza concursos.json, status.json e o cache de editais, e devolve o status."""
    clientes = clientes or {}
    agora = agora or datetime.now(FUSO_BR)
    hoje = agora.date().isoformat()
    anteriores = {c["id"]: c for c in _ler(saida / "concursos.json").get("concursos", [])}
    cache = _ler(cache_editais)
    cache_antes = json.dumps(cache, sort_keys=True)

    # Fontes que não rodaram desta vez continuam com os dados anteriores.
    concursos = {id_: c for id_, c in anteriores.items() if c["banca"] not in fontes}
    status = {}
    for slug in fontes:
        fonte_nova = not any(c["banca"] == slug for c in anteriores.values())
        adaptador = REGISTRO[slug](clientes.get(slug))
        try:
            extraidos = list(adaptador.coletar())
        except Exception as erro:
            log.exception("Coleta de %s falhou", slug)
            mantidos = {id_: c for id_, c in anteriores.items() if c["banca"] == slug}
            concursos.update(mantidos)
            status[slug] = {"ok": False, "concursos": len(mantidos), "erro": f"{type(erro).__name__}: {erro}"[:300]}
            continue
        com_cargos = 0
        for extraido in extraidos:
            anterior = anteriores.get(extraido.chave_externa)
            visto = anterior["primeiro_visto"] if anterior else (None if fonte_nova else hoje)
            leitura = ler_edital(extraido, adaptador.cliente, cache, agora, baixar_editais)
            concursos[extraido.chave_externa] = dados = para_dict(extraido, visto, leitura)
            com_cargos += bool(dados["cargos"])
        status[slug] = {"ok": True, "concursos": len(extraidos), "com_cargos": com_cargos, "erro": ""}
        log.info("%s: %d concursos, %d com cargos", slug, len(extraidos), com_cargos)

    lista = sorted(concursos.values(), key=lambda c: c["id"])
    saida.mkdir(parents=True, exist_ok=True)
    if lista != sorted(anteriores.values(), key=lambda c: c["id"]):
        _gravar(saida / "concursos.json", {"concursos": lista})
    if json.dumps(cache, sort_keys=True) != cache_antes:
        _gravar(cache_editais, dict(sorted(cache.items())))
    resumo = {"gerado_em": _iso(agora), "fontes": status}
    _gravar(saida / "status.json", resumo)
    return resumo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coleta as bancas e gera site/dados/concursos.json.")
    parser.add_argument("fontes", nargs="*", help=f"Padrão: todas ({', '.join(sorted(REGISTRO))}).")
    parser.add_argument("--saida", type=Path, default=SAIDA)
    parser.add_argument("--sem-editais", action="store_true", help="Usa só o cache; não baixa editais novos.")
    args = parser.parse_args(argv)
    desconhecidas = set(args.fontes) - set(REGISTRO)
    if desconhecidas:
        parser.error(f"fonte desconhecida: {', '.join(sorted(desconhecidas))}")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    status = gerar(args.fontes or sorted(REGISTRO), args.saida, baixar_editais=not args.sem_editais)
    return 0 if all(f["ok"] for f in status["fontes"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
