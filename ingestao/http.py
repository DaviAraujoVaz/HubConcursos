"""Cliente HTTP educado: identifica o robô, espera entre requisições e tenta de novo."""
import logging
import time
from urllib.parse import urlparse

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)


class ClienteHttp:
    def __init__(self, intervalo: float | None = None):
        self.sessao = requests.Session()
        self.sessao.headers.update(
            {
                "User-Agent": settings.COLETA_USER_AGENT,
                "Accept-Language": "pt-BR,pt;q=0.9",
            }
        )
        repeticao = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST"),
        )
        self.sessao.mount("https://", HTTPAdapter(max_retries=repeticao))
        self.sessao.mount("http://", HTTPAdapter(max_retries=repeticao))
        self.intervalo = settings.COLETA_INTERVALO_SEG if intervalo is None else intervalo
        self._ultimo_acesso: dict[str, float] = {}

    def _esperar(self, url: str):
        host = urlparse(url).netloc
        decorrido = time.monotonic() - self._ultimo_acesso.get(host, 0)
        if decorrido < self.intervalo:
            time.sleep(self.intervalo - decorrido)
        self._ultimo_acesso[host] = time.monotonic()

    def get(self, url: str, **kwargs) -> requests.Response:
        self._esperar(url)
        kwargs.setdefault("timeout", settings.COLETA_TIMEOUT_SEG)
        log.debug("GET %s", url)
        resposta = self.sessao.get(url, **kwargs)
        resposta.raise_for_status()
        return resposta

    def post(self, url: str, **kwargs) -> requests.Response:
        self._esperar(url)
        kwargs.setdefault("timeout", settings.COLETA_TIMEOUT_SEG)
        resposta = self.sessao.post(url, **kwargs)
        resposta.raise_for_status()
        return resposta
