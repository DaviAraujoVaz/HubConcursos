"""Guarda imutável dos arquivos brutos.

Cada arquivo é salvo pelo hash do conteúdo: o mesmo PDF baixado duas vezes vira
um único arquivo, e nada é sobrescrito. Melhorar um extrator e reprocessar o
histórico não exige baixar nada de novo.
"""
import hashlib
from pathlib import Path

from django.conf import settings


def sha256(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def salvar_bruto(fonte_slug: str, conteudo: bytes, extensao: str) -> tuple[str, str]:
    """Salva e devolve (caminho relativo a DADOS_DIR, sha256)."""
    digest = sha256(conteudo)
    extensao = extensao.lstrip(".").lower() or "bin"
    relativo = Path("bruto") / fonte_slug / digest[:2] / f"{digest}.{extensao}"
    destino = Path(settings.DADOS_DIR) / relativo
    if not destino.exists():
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporario = destino.with_suffix(destino.suffix + ".tmp")
        temporario.write_bytes(conteudo)
        temporario.replace(destino)
    return str(relativo), digest


def ler_bruto(relativo: str) -> bytes:
    return (Path(settings.DADOS_DIR) / relativo).read_bytes()
