"""Configurações do ConcursoHub.

Tudo que muda entre máquinas vem de variáveis de ambiente (ver .env.example).
Sem DATABASE_URL, usa SQLite local — útil para testes rápidos.
Fora do Docker, as variáveis vêm do arquivo .env na raiz do projeto.
"""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def carregar_env(caminho: Path) -> None:
    """Lê KEY=valor do .env. Variáveis já definidas no ambiente (Docker) prevalecem."""
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip("\"'"))


carregar_env(BASE_DIR / ".env")


def env(nome, padrao=None):
    return os.environ.get(nome, padrao)


def env_bool(nome, padrao=False):
    valor = os.environ.get(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "sim", "yes", "on"}


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-inseguro-troque-no-env")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "catalogo",
    "ingestao",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=60,
    )
}
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    # WAL deixa o painel ler enquanto a coleta grava; IMMEDIATE + timeout evitam
    # "database is locked" quando os dois escrevem ao mesmo tempo.
    DATABASES["default"]["OPTIONS"] = {
        "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL",
        "transaction_mode": "IMMEDIATE",
        "timeout": 30,
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Coleta -----------------------------------------------------------------
# Pasta onde ficam os arquivos brutos (imutáveis, nomeados pelo hash).
DADOS_DIR = Path(env("DADOS_DIR", BASE_DIR / "dados"))

# Identificação educada do robô nos sites coletados.
COLETA_USER_AGENT = env(
    "COLETA_USER_AGENT",
    "ConcursoHub/0.1 (uso pessoal; coleta de editais publicos)",
)
COLETA_TIMEOUT_SEG = float(env("COLETA_TIMEOUT_SEG", "30"))
# Pausa entre requisições ao mesmo site, para não sobrecarregar ninguém.
COLETA_INTERVALO_SEG = float(env("COLETA_INTERVALO_SEG", "1.0"))
# Baixar PDFs de editais (True) ou só registrar os links (False).
COLETA_BAIXAR_ARQUIVOS = env_bool("COLETA_BAIXAR_ARQUIVOS", True)

# INLABS (DOU): conta gratuita em https://inlabs.in.gov.br
INLABS_EMAIL = env("INLABS_EMAIL", "")
INLABS_SENHA = env("INLABS_SENHA", "")

# --- Avisos por e-mail -------------------------------------------------------
# Um resumo por dia com o que casou com seus filtros. Sem AVISOS_EMAIL_PARA,
# o resumo vai só para o log.
AVISOS_EMAIL_PARA = env("AVISOS_EMAIL_PARA", "")
# O resumo do dia sai na primeira rotina a partir desta hora (horário de Brasília).
AVISOS_HORA = int(env("AVISOS_HORA", "7"))
# Inscrições que terminam nos próximos N dias entram na seção "Prazos".
AVISOS_DIAS_PRAZO = int(env("AVISOS_DIAS_PRAZO", "7"))
# Concursos listados por resumo; o resto vira "e mais N no painel".
AVISOS_MAX_CONCURSOS = int(env("AVISOS_MAX_CONCURSOS", "40"))
# Endereço do painel, para os links do e-mail.
SITE_URL = env("SITE_URL", "http://localhost:8000").rstrip("/")

EMAIL_HOST = env("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = 30
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "") or EMAIL_HOST_USER or "concursohub@localhost"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simples": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simples"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    # Fontes malformadas em PDFs de banca geram milhares de avisos inofensivos.
    "loggers": {"pdfminer": {"level": "ERROR"}},
}
