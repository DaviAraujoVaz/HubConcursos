"""Coleta as fontes e gera os dados que o site lê.

    python -m concursohub.coletar               # todas as fontes
    python -m concursohub.coletar cebraspe      # só uma (as outras ficam como estavam)

Gera dois arquivos em site/dados/:
- concursos.json: os concursos ativos, já com esfera, áreas e tipo de cada
  documento. Fica no Git e só é reescrito quando algo muda, então o histórico
  do repositório mostra o que mudou em cada coleta.
- status.json: quando a coleta rodou e como foi cada fonte. Não vai para o Git.

Se uma fonte falhar, os concursos dela da coleta anterior são mantidos, para o
site não esvaziar por causa de um site fora do ar. O comando termina com erro
(código 1), o que faz o GitHub Actions avisar por e-mail.
"""
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from .adaptadores import REGISTRO
from .areas import areas_do_concurso
from .classificador import classificar_tipo
from .inferencia import inferir_esfera
from .texto import FUSO_BR

log = logging.getLogger(__name__)

SAIDA = Path(__file__).resolve().parent.parent / "site" / "dados"
# Documentos mais recentes guardados por concurso; o resto fica na página oficial.
MAX_DOCUMENTOS = 15
_MUITO_ANTIGO = datetime.min.replace(tzinfo=FUSO_BR)


def _iso(valor: datetime | None) -> str | None:
    return valor.astimezone(FUSO_BR).isoformat(timespec="minutes") if valor else None


def tipo_do_documento(documento) -> str:
    """O tipo que a fonte informou (ex.: gabaritos da Cebraspe) ou, na falta, o das regras pelo título."""
    return str(documento.tipo if documento.tipo != "outro" else classificar_tipo(documento.titulo))


def para_dict(concurso, primeiro_visto: str | None) -> dict:
    documentos = sorted(concurso.documentos, key=lambda d: d.publicado_em or _MUITO_ANTIGO, reverse=True)
    cargos = [c.nome for c in concurso.cargos]
    return {
        "id": concurso.chave_externa,
        "titulo": concurso.titulo,
        "banca": concurso.banca_slug,
        "situacao": str(concurso.situacao),
        "esfera": str(inferir_esfera(concurso.titulo)),
        "areas": areas_do_concurso(concurso.titulo, cargos),
        "url": concurso.url_oficial,
        "ano": concurso.ano,
        "inscricoes_inicio": _iso(concurso.inscricoes_inicio),
        "inscricoes_fim": _iso(concurso.inscricoes_fim),
        "vagas": concurso.vagas_total,
        "remuneracao_maxima": float(concurso.remuneracao_maxima) if concurso.remuneracao_maxima else None,
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


def gerar(fontes: list[str], saida: Path = SAIDA, clientes: dict | None = None, agora: datetime | None = None) -> dict:
    """Coleta `fontes`, atualiza concursos.json e status.json e devolve o status."""
    clientes = clientes or {}
    agora = agora or datetime.now(FUSO_BR)
    hoje = agora.date().isoformat()
    anteriores = {c["id"]: c for c in _ler(saida / "concursos.json").get("concursos", [])}

    # Fontes que não rodaram desta vez continuam com os dados anteriores.
    concursos = {id_: c for id_, c in anteriores.items() if c["banca"] not in fontes}
    status = {}
    for slug in fontes:
        fonte_nova = not any(c["banca"] == slug for c in anteriores.values())
        try:
            extraidos = list(REGISTRO[slug](clientes.get(slug)).coletar())
        except Exception as erro:
            log.exception("Coleta de %s falhou", slug)
            mantidos = {id_: c for id_, c in anteriores.items() if c["banca"] == slug}
            concursos.update(mantidos)
            status[slug] = {"ok": False, "concursos": len(mantidos), "erro": f"{type(erro).__name__}: {erro}"[:300]}
            continue
        for extraido in extraidos:
            anterior = anteriores.get(extraido.chave_externa)
            visto = anterior["primeiro_visto"] if anterior else (None if fonte_nova else hoje)
            concursos[extraido.chave_externa] = para_dict(extraido, visto)
        status[slug] = {"ok": True, "concursos": len(extraidos), "erro": ""}
        log.info("%s: %d concursos", slug, len(extraidos))

    lista = sorted(concursos.values(), key=lambda c: c["id"])
    saida.mkdir(parents=True, exist_ok=True)
    if lista != sorted(anteriores.values(), key=lambda c: c["id"]):
        (saida / "concursos.json").write_text(
            json.dumps({"concursos": lista}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
    resumo = {"gerado_em": _iso(agora), "fontes": status}
    (saida / "status.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return resumo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coleta as bancas e gera site/dados/concursos.json.")
    parser.add_argument("fontes", nargs="*", help=f"Padrão: todas ({', '.join(sorted(REGISTRO))}).")
    parser.add_argument("--saida", type=Path, default=SAIDA)
    args = parser.parse_args(argv)
    desconhecidas = set(args.fontes) - set(REGISTRO)
    if desconhecidas:
        parser.error(f"fonte desconhecida: {', '.join(sorted(desconhecidas))}")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    status = gerar(args.fontes or sorted(REGISTRO), args.saida)
    return 0 if all(f["ok"] for f in status["fontes"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
