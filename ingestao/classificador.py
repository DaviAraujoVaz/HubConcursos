"""Regras para (1) reconhecer atos sobre concurso e (2) dizer que tipo de ato é.

Regras antes de modelo de linguagem: são explicáveis, rápidas e cobrem a maior
parte dos títulos de edital. O que não casar vira 'outro' e pode ser revisado.
A ordem das regras importa: a primeira que casar vence.
"""
import re

from .models import TipoDocumento
from .texto import normalizar

# Termos que indicam que um ato do diário oficial trata de concurso/seleção.
_TERMOS_CONCURSO = re.compile(
    r"concurso publico|concursos publicos|processo seletivo publico|processo seletivo simplificado"
    r"|selecao publica|provimento de cargos efetivos"
)

# (tipo, padrão no texto normalizado)
_REGRAS_TIPO = [
    # Edital de abertura consolidado ("atualizado conforme retificações",
    # "Edital (retificado em …)") não é retificação: é o edital vigente.
    (TipoDocumento.EDITAL_ABERTURA, r"\babertura\b.{0,40}\b(?:atualizad|consolidad)|^edital \(?(?:retificad|consolidad|atualizad)"),
    # O que a banca intitula "Comunicado – …" é aviso, mesmo citando resultado/recurso.
    (TipoDocumento.COMUNICADO, r"^comunicado\b"),
    (TipoDocumento.HOMOLOGACAO, r"\bhomolog"),
    (TipoDocumento.PRORROGACAO, r"prorroga(?:cao|r|-se)? (?:o )?(?:prazo de )?validade"),
    (TipoDocumento.RETIFICACAO, r"\bretifica|\berrata\b"),
    (TipoDocumento.CONVOCACAO, r"\bconvoca(?:cao|r|dos)\b|\bnomea(?:cao|r)\b"),
    (TipoDocumento.GABARITO, r"\bgabarito"),
    (TipoDocumento.INSCRITOS, r"candidatos? por vaga|demanda de candidatos|relacao (?:final |provisoria )?(?:de|dos) (?:candidatos )?inscritos|inscricoes deferidas"),
    (TipoDocumento.RESULTADO, r"\bresultado|\bclassificacao final|\baprovados\b|nota final"),
    (TipoDocumento.AUTORIZACAO, r"\bautoriza(?:r|cao|-se)? (?:a )?(?:realizacao|abertura) de concurso|\bautoriza (?:o|a) realiza"),
    (TipoDocumento.CONTRATACAO_BANCA, r"(?:extrato|dispensa|inexigibilidade).{0,80}(?:organizacao|realizacao) de concurso|contratacao de (?:empresa|instituicao|banca).{0,60}concurso"),
    (TipoDocumento.EDITAL_ABERTURA, r"\bedital\b.{0,40}\babertura\b|torna publica a (?:abertura|realizacao) de concurso|\babertura de inscricoes\b|edital (?:n[ºo°.]? ?)?1\b"),
    (TipoDocumento.COMUNICADO, r"\bcomunicado\b|\baviso\b"),
]
_REGRAS_COMPILADAS = [(tipo, re.compile(padrao)) for tipo, padrao in _REGRAS_TIPO]


def eh_ato_de_concurso(*textos: str) -> bool:
    return any(_TERMOS_CONCURSO.search(normalizar(t)) for t in textos if t)


def classificar_tipo(titulo: str, texto: str = "") -> str:
    """Tipo do ato pelo título; se o título não decidir, olha o começo do texto."""
    for alvo in (normalizar(titulo), normalizar(texto[:1500])):
        if not alvo:
            continue
        for tipo, padrao in _REGRAS_COMPILADAS:
            if padrao.search(alvo):
                return tipo
    return TipoDocumento.OUTRO
