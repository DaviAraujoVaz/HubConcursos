"""Ferramentas de teste: cliente HTTP falso e acesso às fixtures. Nenhum teste acessa a internet."""
import json
from pathlib import Path

import requests

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(nome: str) -> bytes:
    return (FIXTURES / nome).read_bytes()


class RespostaFalsa:
    def __init__(self, conteudo: bytes, status: int = 200):
        self.content = conteudo
        self.status_code = status
        self.text = conteudo.decode("utf-8", errors="replace")

    def json(self):
        return json.loads(self.content)


class ClienteFalso:
    """Responde a URLs a partir de um dicionário {url: bytes}. URL ausente → HTTPError 404."""

    def __init__(self, respostas: dict[str, bytes]):
        self.respostas = respostas
        self.pedidos: list[str] = []

    def get(self, url, **kwargs):
        self.pedidos.append(url)
        if url not in self.respostas:
            raise requests.HTTPError(f"404 para {url}")
        return RespostaFalsa(self.respostas[url])
