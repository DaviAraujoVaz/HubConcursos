"""Ferramentas de teste: cliente HTTP falso e acesso às fixtures."""
import json
import shutil
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings

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

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"{self.status_code}", response=self)


class CookiesFalsos(dict):
    def get(self, chave, padrao=None):
        return super().get(chave, padrao)


class SessaoFalsa:
    def __init__(self):
        self.cookies = CookiesFalsos()


class ClienteFalso:
    """Responde a URLs a partir de um dicionário {url: bytes}. URL ausente → 404."""

    def __init__(self, respostas: dict[str, bytes], ao_postar=None):
        self.respostas = respostas
        self.pedidos: list[str] = []
        self.sessao = SessaoFalsa()
        self.ao_postar = ao_postar

    def get(self, url, **kwargs):
        self.pedidos.append(url)
        if url not in self.respostas:
            resposta = RespostaFalsa(b"", 404)
            resposta.raise_for_status()
        return RespostaFalsa(self.respostas[url])

    def post(self, url, **kwargs):
        self.pedidos.append(url)
        if self.ao_postar:
            self.ao_postar(self)
        return RespostaFalsa(b"ok")


class TesteComDados(TestCase):
    """Isola a pasta de arquivos brutos em um diretório temporário."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._dados = tempfile.mkdtemp(prefix="concursohub-teste-")
        cls._override = override_settings(DADOS_DIR=Path(cls._dados), COLETA_INTERVALO_SEG=0)
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        shutil.rmtree(cls._dados, ignore_errors=True)
        super().tearDownClass()
