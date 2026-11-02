"""Cargos e remuneração lidos do edital de abertura (PDF).

As bancas não publicam isso de forma estruturada: a Cebraspe só dá os nomes dos
cargos e o maior salário, e a FGV nem os cargos. O edital tem tudo, em três
formatos principais:

- "CARGO N: NOME" (Cebraspe), seguido de requisitos, atribuições e
  "REMUNERAÇÃO: R$ 5.667,92". Às vezes a remuneração vem uma vez só, antes de um
  grupo de cargos ("SUBSÍDIO INICIAL: R$ 20.000,00" e depois CARGO 1…4).
- Subitens da seção de cargos ("2 DOS CARGOS / 2.1 TÉCNICO UNIVERSITÁRIO…"),
  cada um com a sua remuneração.
- Quadro de vagas (FGV): na seção "DOS CARGOS", uma tabela com o nome do
  cargo/perfil/especialidade, os números de vagas e, às vezes, o vencimento.
  O texto do PDF quebra os nomes em várias linhas, e quadro_de_vagas() junta os
  pedaços. O quadro também pode estar num anexo ("ANEXO VII – DISTRIBUIÇÃO DE
  VAGAS POR UF", com uma linha por UF), e a remuneração, em outro
  ("ANEXO III – REMUNERAÇÃO… CARGO: ANALISTA… R$ …"). Por isso o PDF é lido inteiro.

Tudo aqui é heurística: o que não dá para ler com segurança fica de fora, e o
concurso continua com as áreas do título. Caso novo: salve o trecho do edital em
tests/fixtures/editais/ e escreva um teste em tests/test_edital.py.
"""
import io
import re
from dataclasses import dataclass
from decimal import Decimal

from .texto import limpar_espacos, normalizar, parse_decimal

# Mude quando a extração mudar: os editais já lidos serão lidos de novo.
VERSAO = 7
# Editais grandes (Ebserh, MPU) põem o quadro de vagas em anexo, depois da página 100.
MAX_PAGINAS = 400


@dataclass
class CargoEdital:
    nome: str
    remuneracao: Decimal | None = None
    numero: int | None = None


# --- Qual documento é o edital -------------------------------------------------

def escolher_edital(documentos, tipo_de):
    """O edital de abertura mais atual, em PDF. O consolidado ("atualizado
    conforme retificações", "Edital (retificado em…)") vence o original."""
    candidatos = []
    for posicao, doc in enumerate(documentos):
        if tipo_de(doc) != "edital_abertura" or not doc.url.lower().endswith(".pdf"):
            continue
        titulo = normalizar(doc.titulo)
        consolidado = bool(re.search(r"atualizad|consolidad|retificad", titulo))
        data = doc.publicado_em.timestamp() if doc.publicado_em else 0
        candidatos.append(((consolidado, data, -posicao), doc))
    return max(candidatos, key=lambda c: c[0])[1] if candidatos else None


def texto_do_pdf(conteudo: bytes, max_paginas: int = MAX_PAGINAS) -> str:
    import pypdfium2 as pdfium

    documento = pdfium.PdfDocument(io.BytesIO(conteudo))
    try:
        partes = []
        for indice in range(min(len(documento), max_paginas)):
            pagina = documento[indice]
            texto = pagina.get_textpage()
            partes.append(texto.get_text_range())
            texto.close()
            pagina.close()
    finally:
        documento.close()
    return _limpar_texto("\n".join(partes))


def _limpar_texto(texto: str) -> str:
    # pdfium separa linhas com \r\n, marca o hífen de quebra de linha com U+FFFE, e
    # alguns editais usam espaço não separável no lugar do espaço comum.
    return texto.replace("\r\n", "\n").replace("\r", "\n").replace("￾", "-").replace("\xa0", " ")


# --- Valores em reais ----------------------------------------------------------

_VALOR = r"(?:R\$\s*)+(\d{1,3}(?:\.\d{3})*,\d{2})"
_ROTULO_SALARIO = re.compile(
    r"(?:REMUNERA[ÇC][ÃA]O|SUBS[ÍI]DIO|VENCIMENTO|SAL[ÁA]RIO)[^\n:]{0,120}?:?\s*" + _VALOR, re.IGNORECASE
)
# Abaixo disso é taxa de inscrição ou auxílio, não salário.
SALARIO_MINIMO_PLAUSIVEL = Decimal("1000")


def _reais(texto: str) -> Decimal | None:
    valor = parse_decimal(texto.replace(".", "").replace(",", "."))
    return valor if valor and valor >= SALARIO_MINIMO_PLAUSIVEL else None


# --- Seção "DOS CARGOS" --------------------------------------------------------

_SECAO_CARGOS = re.compile(r"(?m)^[ \t]*(\d+)\.?[ \t]*DOS?[ \t]+CARGOS?\b.*$", re.IGNORECASE)


_SECAO_VAGAS = re.compile(
    r"(?m)^[ \t]*(\d+)\.?[ \t]*DAS[ \t]+VAGAS\b(?![ \t]+(?:DESTINADAS|RESERVADAS|PARA))[^\n]*$", re.IGNORECASE
)


def _secao_cargos(texto: str) -> tuple[int, int]:
    """(início, fim) da seção de cargos ("3. DOS CARGOS", "4. DAS VAGAS"), ou (0, 0)."""
    m = _SECAO_CARGOS.search(texto) or _SECAO_VAGAS.search(texto)
    if not m:
        return 0, 0
    numero = int(m.group(1))
    # Termina no próximo item principal ("4. DAS INSCRIÇÕES") ou num subitem
    # em texto corrido ("3.2 Para investidura no cargo…").
    fim = re.compile(rf"(?m)^[ \t]*(?:{numero + 1}\.?[ \t]+D[AOE]S?[ \t]|{numero}\.[2-9][ \t]+[A-Z][a-zà-ú])")
    proximo = fim.search(texto, m.end())
    return m.end(), proximo.start() if proximo else min(len(texto), m.end() + 15000)


# --- Formatos 1 e 2: blocos com cabeçalho e remuneração ------------------------

_CABECALHO = re.compile(r"(?m)^[ \t]*(?:\d+(?:\.\d+)*\.?[ \t]+)?CARGO[ \t]+(\d{1,3})[ \t]*:[ \t]*(.+)$")
_SUBITEM = re.compile(r"(?m)^[ \t]*\d+(?:\.\d+)+\.?[ \t]+(\S[^\n]{4,150})$")
_ROTULOS_DE_BLOCO = re.compile(
    r"^(?:REQUISITO|ATRIBUI|DESCRI|REMUNERA|SUBS[ÍI]DIO|VENCIMENTO|SAL[ÁA]RIO|JORNADA|CARGA|LOTA|VAGAS|\d)", re.IGNORECASE
)


def _maiusculas(linha: str) -> bool:
    letras = [c for c in linha if c.isalpha()]
    return bool(letras) and sum(c.isupper() for c in letras) / len(letras) > 0.8


def _nome_com_continuacao(texto: str, m: re.Match, grupo: int) -> tuple[str, int]:
    """Nome do cabeçalho, juntando as linhas seguintes quando o PDF quebrou o nome."""
    nome, fim = m.group(grupo).strip(), m.end()
    for linha in texto[m.end():m.end() + 400].split("\n")[1:3]:
        if nome.endswith((".", ";")) or not _maiusculas(linha) or _ROTULOS_DE_BLOCO.match(linha.strip()) or _CABECALHO.match(linha):
            break
        nome = f"{nome} {linha.strip()}"
        fim += len(linha) + 1
    return limpar_espacos(nome), fim


def cargos_numerados(texto: str) -> list[CargoEdital]:
    """Formato "CARGO N: NOME"."""
    cabecalhos, vistos = [], set()
    for m in _CABECALHO.finditer(texto):
        numero = int(m.group(1))
        if numero in vistos:  # o anexo de conteúdo repete os cargos; vale a primeira vez
            continue
        vistos.add(numero)
        nome, fim = _nome_com_continuacao(texto, m, 2)
        cabecalhos.append((m.start(), fim, numero, nome))
    return _com_remuneracao(texto, cabecalhos)


def cargos_em_subitens(texto: str) -> list[CargoEdital]:
    """Formato "2 DOS CARGOS / 2.1 TÉCNICO UNIVERSITÁRIO (NÍVEL SUPERIOR)"."""
    inicio, fim_secao = _secao_cargos(texto)
    if not fim_secao:
        return []
    numero = (_SECAO_CARGOS.search(texto) or _SECAO_VAGAS.search(texto)).group(1)
    subitem = re.compile(rf"(?m)^[ \t]*{numero}\.(\d+)\.?[ \t]+([A-ZÀ-Ú][^\n]{{2,150}})$")
    cabecalhos = []
    for m in subitem.finditer(texto, inicio, fim_secao):
        rotulo = m.group(2)
        if not _maiusculas(rotulo) or normalizar(rotulo).startswith(("dos ", "das ", "do ", "da ")):
            continue
        nome, fim = _nome_com_continuacao(texto, m, 2)
        cabecalhos.append((m.start(), fim, int(m.group(1)), nome))
    cargos = _com_remuneracao(texto, cabecalhos, fim_secao)
    # Sem remuneração em nenhum subitem, provavelmente não são cargos.
    return cargos if any(c.remuneracao for c in cargos) else []


def _com_remuneracao(texto: str, cabecalhos: list, fim_maximo: int | None = None) -> list[CargoEdital]:
    if not cabecalhos:
        return []
    inicio_regiao = max(0, cabecalhos[0][0] - 4000)
    fim_regiao = cabecalhos[-1][1] + 6000
    if fim_maximo:
        fim_regiao = min(fim_regiao, fim_maximo)
    salarios = [(m.start(), _reais(m.group(1))) for m in _ROTULO_SALARIO.finditer(texto, inicio_regiao, fim_regiao)]
    salarios = [(pos, valor) for pos, valor in salarios if valor]

    # Títulos de grupo ("2.2 TÉCNICO UNIVERSITÁRIO DE SUPORTE", "2.2 DOS CARGOS DE AUDITOR"):
    # a remuneração depois deles é do grupo seguinte, não do cargo anterior.
    grupos = [
        m.start() for m in _SUBITEM.finditer(texto, inicio_regiao, fim_regiao)
        if _maiusculas(m.group(1)) and not _CABECALHO.match(m.group(0))
    ]

    # Remuneração "própria": a primeira entre o cabeçalho do cargo e o próximo cabeçalho ou grupo.
    proprias = {}
    for i, (_, fim, numero, _) in enumerate(cabecalhos):
        limite = cabecalhos[i + 1][0] if i + 1 < len(cabecalhos) else fim_regiao
        limite = min([limite] + [g for g in grupos if g > fim])
        proprias[numero] = next(((pos, valor) for pos, valor in salarios if fim <= pos < limite), None)
    posicoes_proprias = {p[0] for p in proprias.values() if p}

    cargos = []
    for inicio, _, numero, nome in cabecalhos:
        if proprias[numero]:
            valor = proprias[numero][1]
        else:
            # Herda a remuneração de um grupo declarada antes (ex.: "SUBSÍDIO INICIAL"
            # antes de CARGO 1…4), desde que não seja a própria de outro cargo.
            anteriores = [v for p, v in salarios if p < inicio and p not in posicoes_proprias]
            valor = anteriores[-1] if anteriores else None
        cargos.append(CargoEdital(nome=nome, remuneracao=valor, numero=numero))
    return cargos


# --- Formato 3: quadro de vagas ------------------------------------------------

# Palavras de cabeçalho de tabela: uma linha só com elas não é nome de cargo.
_CABECALHO_TABELA = set(
    "cargo cargos especialidade especialidades perfil perfis area areas codigo cod nivel superior medio fundamental "
    "escolaridade requisito requisitos carga horaria semanal semanais vencimento vencimentos base basico "
    "remuneracao salario subsidio inicial total de vagas vaga imediatas cadastro reserva cr ac pcd pn pp pi pq ppp "
    "negro negros indigena indigenas quilombola quilombolas afrodescendentes pretos pardos hipossuficientes "
    "economicos candidatos candidato pessoa ampla concorrencia localidade localidades lotacao municipio regiao "
    "quadro e do da das dos para pessoas com deficiencia valor taxa inscricao h horas habilitacao incompleto "
    "completo publico efetivo candidat indios os ou minoria etnico racial etnico-racial semana formacao "
    "macrorregiao n i q".split()
)
# Sinais de que a "linha da tabela" não é um cargo (nota, requisito, cabeçalho de página).
_LIXO = re.compile(
    r"\bedital\b|\bprefeitura de\b|reconhecid|\bcomplet[oa]\b|aproximadamente|\btotal\b|\bmec\b|\bp[aá]gina\b"
    r"|\blegenda\b|imediatas|ampla concorr|\bnegros\b|\bpardos\b|fornecid|institui[çc][ãa]o|secretaria de estado"
    r"|\bdepend[êe]ncias\b|\bS\.A\.",
    re.IGNORECASE,
)
_CAUDA_NUMERICA = re.compile(
    r"(?:\s+(?:R\$\s*[\d.,]+|[\d.]+,\d{2}|\d+\s*horas?|\d+[hH]\b|\d+\s*[hH]\b|\d+|CR|\+|-|–|\*+"
    r"|FUNDAMENTAL|M[ÉE]DIO|SUPERIOR))+\s*$"
)
_SO_NUMEROS = re.compile(r"^(?:R\$\s*[\d.,]+|[\d.]+,\d{2}|\d+[hH]?|CR|\+|-|–|\*+|\s)+$")
# Valor sem "R$" (coluna "Remuneração (R$)"): só com separador de milhar, para não pegar vagas.
_VALOR_SOLTO = r"\b(\d{1,3}(?:\.\d{3})+,\d{2})\b"
_UFS = set("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())
_SIGLAS_UF = "AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO"
_LOCALIDADE = re.compile(
    rf"/\s*[A-Z]{{2}}\b|/\s*$|\s[–-]\s*(?:{_SIGLAS_UF})\b|^Regi[ãa]o\s+[IVX]+\b|^Polo\b", re.IGNORECASE
)
_CORTE_NOME = re.compile(r"\b(?:diploma|certificado|curso|graduac|conclus|ensino|registro)", re.IGNORECASE)
_PREFIXO_CARGO = re.compile(r"\bCARGO(?:/ESPECIALIDADE)?\s*:\s*(.+)$", re.IGNORECASE)


_CONECTIVOS = {"de", "da", "do", "das", "dos", "e", "para", "com"}


def _so_cabecalho(texto: str) -> bool:
    palavras = re.findall(r"[a-z]+", normalizar(texto))
    # Só conectivos ("DE") é pedaço de nome quebrado, não cabeçalho.
    return bool(set(palavras) - _CONECTIVOS) and all(p in _CABECALHO_TABELA for p in palavras)


_PALAVRAS_CURTAS = {"de", "da", "do", "das", "dos", "e", "em", "a", "o", "as", "os", "no", "na", "ti", "tic"}


def _juntar(pedacos: list[str]) -> str:
    """Junta as linhas de um nome. Palavra cortada pelo PDF ("PROCESSAMEN" + "TO") volta inteira."""
    nome = ""
    for pedaco in pedacos:
        primeira = pedaco.split(" ")[0]
        cortada = re.fullmatch(r"[A-ZÀ-Ú]{1,3}", primeira) and primeira.lower() not in _PALAVRAS_CURTAS
        if nome and cortada and nome[-1].isupper():
            nome += pedaco
        else:
            nome = f"{nome} {pedaco}" if nome else pedaco
    return nome


def _sem_localidade(nome: str) -> str:
    """"8. CONTABILIDADE Brasília / DF" → "8. CONTABILIDADE"; "Rio de Janeiro / RJ" → ""."""
    if not _LOCALIDADE.search(nome):
        return nome
    palavras = []
    for palavra in nome.split():
        if not (palavra.isupper() or re.fullmatch(r"\d+\.?", palavra) or palavra in ("–", "-")):
            break
        palavras.append(palavra)
    return " ".join(palavras)


def _parece_cargo(nome: str) -> bool:
    if _LIXO.search(nome) or re.search(r"\d{2,}", nome):
        return False
    # Tabela de lotação ("AP Macapá HU-UNIFAP Hospital Universitário…"), não de cargos.
    if re.match(r"^[A-Z]{2}\s+[A-ZÀ-Ú][a-zà-ú]", nome):
        return False
    palavras = re.findall(r"[a-z]{3,}", normalizar(nome))
    return any(p not in _CABECALHO_TABELA and p not in _CONECTIVOS for p in palavras)


def _sem_cabecalho_nas_pontas(nome: str) -> str:
    """"Hipossuficientes Econômicos Total Procurador Legislativo 3 CR*" → "Procurador Legislativo"."""
    def descartavel(palavra: str) -> bool:
        limpa = normalizar(palavra).strip("*:;,.()")
        return limpa in _CABECALHO_TABELA or bool(re.fullmatch(r"[\d.,*+x]+|cr\**", limpa))

    palavras = nome.split()
    # No começo, também cai resto de cabeçalho em minúsculas ("ou pardos) Juiz Substituto"):
    # nome de cargo começa com maiúscula.
    while palavras and (descartavel(palavras[0]) or not palavras[0][0].isupper()):
        palavras.pop(0)
    while palavras and descartavel(palavras[-1]):
        palavras.pop()
    return " ".join(palavras)


def _limpar_nome(nome: str) -> str:
    nome = _sem_localidade(limpar_espacos(nome))
    nome = re.split(r"\s*R\$", nome)[0]  # "… Especialidade Direito R$ 7.405,92 Aproximadamente…"
    # Colunas de vagas grudadas no nome: "Professor de Arte 1 (A) 1 (A)…", "Veterinária - - - -".
    nome = re.split(r"\s+\d+\s*\([A-Z]\)|\s+-\s+-|\s+\d+(?:\s+\d+)+\b", nome)[0]
    if len(nome) > 110:  # requisito grudado no nome; fica o começo
        nome = nome[:110].rsplit(" ", 1)[0] + "…"
    nome = _sem_cabecalho_nas_pontas(nome)
    nome = _CORTE_NOME.split(nome)[0]
    nome = re.sub(r"^\d+\s*[.\-–)]?\s*", "", nome)  # "1. ANÁLISE DE NEGÓCIO" → "ANÁLISE DE NEGÓCIO"
    nome = re.split(r"\s+Regi[ãa]o\s+[IVX]+\b", nome)[0]
    nome = re.sub(r"\s*[–-]?\s*Classe\s+[A-Z]\b.*$", "", nome)
    # Cabeçalho de página em maiúsculas grudado no começo ("EMPRESA BRASILEIRA DE SERVIÇOS
    # HOSPITALARES … Médico - Cardiologia"): sai, se o resto do nome é em caixa normal.
    cabecalho = re.match(r"^(?:[A-ZÀ-Ú0-9][A-ZÀ-Ú0-9.\-–]*\s+){3,}(?=[A-ZÀ-Ú][a-zà-ú])", nome)
    if cabecalho:
        nome = nome[cabecalho.end():]
    return _sem_cabecalho_nas_pontas(nome.strip(" ,;:–-")).strip(" ,;:–-")


_ANEXO = re.compile(r"(?m)^[ \t]*ANEXO\s+[IVXL]+\b[^\n]*$", re.IGNORECASE)
_ANEXO_DE_QUADRO = re.compile(r"vaga|cargo|quadro|salari|remunera")
_ANEXO_DE_OUTRA_COISA = re.compile(
    r"atribui|conteudo|perfil profiss|cronograma|modelo|declara|requerimento|formulario|laudo|titulos|autodeclara"
)


def regioes_de_quadro(texto: str) -> list[tuple[int, int]]:
    """Onde pode haver quadro de vagas: a seção de cargos e os anexos de vagas/cargos
    ("ANEXO VII – DISTRIBUIÇÃO DE VAGAS POR UF", "ANEXO VI – DO CARGO")."""
    regioes = []
    inicio, fim = _secao_cargos(texto)
    if fim:
        regioes.append((inicio, fim))
    cabecalhos = list(_ANEXO.finditer(texto))
    for i, m in enumerate(cabecalhos):
        titulo = normalizar(texto[m.start(): m.end() + 150])  # o título às vezes continua na linha de baixo
        if not _ANEXO_DE_QUADRO.search(titulo) or _ANEXO_DE_OUTRA_COISA.search(titulo):
            continue
        proximo = cabecalhos[i + 1].start() if i + 1 < len(cabecalhos) else len(texto)
        if proximo - m.end() < 300:  # linha do sumário ("Anexo II – Quadro de Vagas;"), não o anexo
            continue
        regioes.append((m.end(), min(proximo, m.end() + 30000)))
    return regioes


def quadro_de_vagas(texto: str, inicio: int | None = None, fim: int | None = None) -> list[CargoEdital]:
    if inicio is None:
        inicio, fim = _secao_cargos(texto)
    cargos: list[CargoEdital] = []
    pedacos: list[str] = []
    prefixo = ""
    linhas_lidas = 0
    for linha in texto[inicio:fim].split("\n"):
        linha = linha.strip()
        normal = normalizar(linha)
        # Rodapé de página ("DATAPREV | CONCURSO PÚBLICO 2026 3"), totais e notas.
        if not linha or "|" in linha or normal.startswith(("total", "*")) or "concurso publico" in normal:
            continue
        if re.match(r"^\d+\.\d+\s", linha):  # "3.1 A denominação dos cargos…"
            pedacos = []
            continue
        grupo = _PREFIXO_CARGO.search(linha)
        if grupo and not _CAUDA_NUMERICA.search(linha):  # "NÍVEL SUPERIOR – CARGO: ANALISTA"
            prefixo, pedacos = limpar_espacos(grupo.group(1)), []
            continue
        cauda = None if _SO_NUMEROS.match(linha) else _CAUDA_NUMERICA.search(linha)
        if cauda and not re.search(r"\d|CR", cauda.group()):  # "TI –": o nome continua na linha de baixo
            cauda = None
        texto_linha = "" if _SO_NUMEROS.match(linha) else (linha[: cauda.start()].strip() if cauda else linha)
        if cauda and texto_linha.upper() in _UFS:  # "AC 1 CR 1 CR 2 + CR": linha de UF, não cabeçalho
            texto_linha = ""
        if texto_linha and (_so_cabecalho(texto_linha) or normal.startswith(("carga horaria", "vencimento", "remuneracao"))):
            if not (cauda and pedacos):
                pedacos = []
                continue
            texto_linha = ""  # "semanais R$ 10.577,48": resto de coluna; a linha fecha o cargo de cima
        if not cauda and not _SO_NUMEROS.match(linha):
            pedacos.append(texto_linha)
            continue
        # Linha com números: fecha uma linha da tabela.
        if texto_linha:
            pedacos.append(texto_linha)
        if pedacos:
            nome = _limpar_nome(_juntar(pedacos))
            valor = re.search(_VALOR, linha) or re.search(_VALOR_SOLTO, linha)
            if valor and not _reais(valor.group(1)):  # "Nível Superior - Direito R$ 340,00": tabela de taxas
                pedacos = []
                continue
            if 3 <= len(nome) <= 160:
                linhas_lidas += 1
                if _parece_cargo(nome):
                    if prefixo and not normalizar(nome).startswith(normalizar(prefixo)):
                        nome = f"{prefixo} – {nome}"
                    cargos.append(CargoEdital(nome=nome, remuneracao=_reais(valor.group(1)) if valor else None))
        pedacos = []

    # Muita linha que não parece cargo: a tabela não foi entendida; melhor não mostrar nada.
    if linhas_lidas and len(cargos) < 0.6 * linhas_lidas:
        return []

    # O mesmo nome em várias linhas (uma por localidade) vira um cargo só.
    unicos: dict[str, CargoEdital] = {}
    for cargo in cargos:
        anterior = unicos.setdefault(normalizar(cargo.nome), cargo)
        if anterior.remuneracao is None:
            anterior.remuneracao = cargo.remuneracao
    resultado = list(unicos.values())
    # Centenas de nomes diferentes é tabela de lotação (escola, diretoria regional), não de cargos.
    if len(resultado) > 200:
        return []
    _remuneracao_do_anexo(texto, resultado)
    return resultado


_ANEXO_CARGO = re.compile(r"(?m)^[ \t]*CARGO\s*:?\s*(.+)$")


def _remuneracao_do_anexo(texto: str, cargos: list[CargoEdital]) -> None:
    """Completa a remuneração com um anexo do tipo "ANEXO III – REMUNERAÇÃO… /
    CARGO: ANALISTA DE TI (Todos os perfis) / … R$ a R$ b R$ c"."""
    if not cargos or all(c.remuneracao for c in cargos):
        return
    titulo = re.search(r"(?m)^[ \t]*ANEXO\s+[IVX]+\s*[–-]\s*REMUNERA", texto)
    if not titulo:
        return
    trecho = texto[titulo.end(): titulo.end() + 4000]
    tabela = []
    for m in _ANEXO_CARGO.finditer(trecho):
        bloco = trecho[m.end(): m.end() + 400].split("CARGO")[0]
        linha_de_valores = next((linha for linha in bloco.split("\n") if re.search(_VALOR, linha)), "")
        valores = re.findall(_VALOR, linha_de_valores)
        if valores:
            # Na linha de valores, a última coluna é a remuneração total ("REMUNERAÇÃO INICIAL").
            tabela.append((m.group(1), _reais(valores[-1])))
    padrao = next((v for rotulo, v in tabela if re.search(r"todos os perfis|todas as especialidades", rotulo, re.I)), None)
    for cargo in cargos:
        if cargo.remuneracao:
            continue
        nome = normalizar(cargo.nome)
        for rotulo, valor in tabela:
            nucleo = normalizar(re.sub(r"\(.*?\)", "", rotulo)).strip()
            if nucleo and nucleo in nome:
                cargo.remuneracao = valor
                break
        else:
            cargo.remuneracao = padrao


# --- Ponto de entrada ----------------------------------------------------------

def analisar(texto: str) -> list[CargoEdital]:
    """Cargos (com remuneração, quando houver) encontrados no texto do edital.
    Tenta os três formatos e fica com o que achou mais cargos com remuneração."""
    texto = _limpar_texto(texto)
    opcoes = [cargos_numerados(texto), cargos_em_subitens(texto)]
    opcoes += [quadro_de_vagas(texto, inicio, fim) for inicio, fim in regioes_de_quadro(texto)]
    return max(opcoes, key=lambda cargos: (sum(1 for c in cargos if c.remuneracao), len(cargos)))


def remuneracao_unica(texto: str) -> Decimal | None:
    """A remuneração da seção de cargos (ou do começo do edital, se não houver
    seção) quando há um valor só: edital de um cargo."""
    texto = _limpar_texto(texto)
    inicio, fim = _secao_cargos(texto)
    if not fim:
        inicio, fim = 0, min(len(texto), 20000)
    valores = {_reais(m.group(1)) for m in _ROTULO_SALARIO.finditer(texto, inicio, fim)} - {None}
    return valores.pop() if len(valores) == 1 else None
