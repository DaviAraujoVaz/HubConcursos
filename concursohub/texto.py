"""Funções pequenas de texto e datas usadas por todos os adaptadores."""
import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

FUSO_BR = ZoneInfo("America/Sao_Paulo")


def normalizar(texto: str) -> str:
    """Minúsculas, sem acentos e com espaços simples. Base de toda comparação."""
    if not texto:
        return ""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


def limpar_espacos(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


_DATA_BR = re.compile(r"(\d{2})/(\d{2})/(\d{4})(?:\D+(\d{1,2})[:h](\d{2}))?")


def parse_data_br(texto: str):
    """'09/10/2026 10:00' → datetime com fuso de Brasília. Sem hora → 00:00."""
    if not texto:
        return None
    m = _DATA_BR.search(texto)
    if not m:
        return None
    dia, mes, ano, hora, minuto = m.groups()
    try:
        return datetime(int(ano), int(mes), int(dia), int(hora or 0), int(minuto or 0), tzinfo=FUSO_BR)
    except ValueError:
        return None


def parse_periodo_br(texto: str):
    """'De 10/10/2026 até 04/11/2026 às 18:00' → (inicio, fim)."""
    if not texto:
        return None, None
    datas = list(_DATA_BR.finditer(texto))
    if not datas:
        return None, None
    inicio = parse_data_br(datas[0].group(0))
    fim = parse_data_br(texto[datas[1].start():]) if len(datas) > 1 else None
    return inicio, fim


def parse_iso(texto: str):
    """ISO 8601 da fonte; sem fuso → assume Brasília."""
    if not texto:
        return None
    try:
        valor = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=FUSO_BR)
    return valor


def parse_decimal(valor):
    if valor in (None, "", 0, "0"):
        return None
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None
    return numero if numero > 0 else None


def parse_inteiro(valor):
    if valor in (None, ""):
        return None
    digitos = re.sub(r"\D", "", str(valor))
    return int(digitos) if digitos else None
