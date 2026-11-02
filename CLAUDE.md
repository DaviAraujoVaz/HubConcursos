# ConcursoHub — contexto para o Claude Code

Site **pessoal** do Davi para consultar concursos públicos: quais estão com inscrições abertas, previstos ou em andamento. Um único usuário, sem contas.

Código, nomes, mensagens e documentação são em **português**. Mantenha assim.

## Escopo atual: MVP estático e gratuito (desde 02/11/2026)

O Davi pediu um MVP utilizável, **sem custo e sem depender de servidor nem do PC dele**:

```
GitHub Actions (cron a cada 6 h) → python -m concursohub.coletar → site/dados/concursos.json → GitHub Pages
```

- **Sem banco, sem Django, sem download de PDF.** A coleta só lê metadados (título, situação, datas, cargos, links dos documentos).
- **Repositório público** (exigência do GitHub Pages gratuito). Nunca grave segredos no repositório.
- **Sem avisos por e-mail no MVP**, por escolha do Davi. Se voltar a ser pedido, o caminho é o Actions comparar o JSON novo com o anterior.
- A versão anterior (Django + Postgres/SQLite, PDFs, OCR planejado, estatísticas, resumo por e-mail, DOU) está na tag **`django-completo`**. Não reintroduza essas peças sem pedido explícito: elas exigem servidor e foram cortadas de propósito.

## Decisões que continuam valendo

- **Fontes oficiais primeiro.** Os dados vêm dos sites das bancas. Agregadores (PCI, blogs) não são fonte.
- **Fontes como plugins.** Cada banca é um adaptador em `concursohub/adaptadores/` que só devolve `ConcursoExtraido`/`DocumentoExtraido`. Classificar e gravar fica em `coletar.py`, igual para todas.
- **Área de atuação e esfera são filtros independentes:** um "Analista de TI de tribunal" entra em Tribunais **e** em TI.
- **Robustez:** se uma fonte falhar, `coletar.py` mantém os dados anteriores dela e sai com código 1 (o job do Actions fica vermelho e o GitHub manda e-mail).
- **"Novo":** `primeiro_visto` fica vazio para o acervo da primeira coleta de cada fonte; depois, é a data em que o concurso apareceu.
- **LGPD:** não colete nem publique listas nominais de resultado.

## Preferências do Davi

- Bancas que mais acompanha: **FGV e Cebraspe**.
- Filtros que importam: **área de atuação** (TI, Tribunais, Fiscal, Controle, Policial…) e **esfera** (federal/estadual/distrital/municipal).
- Ambiente: Windows (`C:\Users\davia\ProjetosPessoais\HubConcursos`), Python 3.13 em `.venv`.

## Como as fontes funcionam (mapeado em 29/10/2026)

- **Cebraspe** (`adaptadores/cebraspe.py`): API JSON que o próprio site consome.
  - Lista: `https://apis.cebraspe.org.br/cebraspe/eventos/tipo/concursos/` (fases: novos, inscricoes-abertas, em-andamento, encerrado).
  - Detalhe: `https://apis.cebraspe.org.br/cebraspe/eventos/<eventoURL>` (eventoCargos, arquivosEdital, arquivosGabarito, periodoInscricao).
  - PDFs: `https://cdn.cebraspe.org.br/concursos/<eventoURL>/arquivos/<nomeArquivo>`. A versão `.html` (VLibras) de cada arquivo é ignorada.
  - Às vezes `eventoNomeCompleto` vem igual ao slug ("ADEAL_26"); aí usa a abreviação.
- **FGV** (`adaptadores/fgv.py`): HTML de Drupal. Lista em `conhecimento.fgv.br/concursos?page=N` (`.view-id-concursos_em_andamento` / `concursos_realizados`). No detalhe: título em `<h1>`, situação em `.field--name-field-concurso-status`, arquivos em `.paragraph--type--texto-data`. Páginas índice sem arquivos (ex.: Macaé) apontam para `<url>/1`, `/2`…, e cada subpágina vira um concurso. Não há cargos nem datas de inscrição.

## Estrutura

```
concursohub/
  adaptadores/   base.py (dataclasses + REGISTRO), cebraspe.py, fgv.py
  coletar.py     roda os adaptadores, classifica, grava site/dados/concursos.json e status.json
  areas.py       taxonomia de áreas e termos (palavra inteira; "*" no fim = prefixo)
  inferencia.py  esfera pelo título
  classificador.py  tipo de documento; a ordem das regras importa
  modelos.py     Situacao, Esfera, TipoDocumento
  http.py        cliente educado (User-Agent, 1 s entre requisições, retry)
site/            index.html, app.js, estilo.css, dados/concursos.json (status.json não vai para o Git)
tests/           unittest com fixtures reais; nenhum teste acessa a internet
.github/workflows/coletar.yml
```

## Comandos

```bash
python -m unittest                       # rodar sempre antes de concluir
python -m concursohub.coletar            # ou: python -m concursohub.coletar cebraspe
python -m http.server -d site 8000       # ver o site local
```

## Convenções ao mexer no código

- **Nova fonte:** adaptador com `@registrar`, import em `adaptadores/__init__.py`, nome em `BANCAS` no `site/app.js`, resposta real em `tests/fixtures/` e um teste.
- **Site mudou de layout:** a correção fica só no adaptador daquela fonte. Atualize a fixture.
- **Classificação errada** (tipo de documento, área ou esfera): adicione o caso em `tests/test_classificacao.py` antes de ajustar a regra. Casos reais já cobertos: "Edital (retificado em…)" é edital de abertura, não retificação; "Comunicado – … resultado…" é comunicado; "para" não é o estado do Pará.
- **Coleta educada:** use sempre `concursohub/http.py`.
- **Site sem build:** HTML/CSS/JS puros, sem dependências externas. Precisa funcionar no celular e no modo escuro.

## Próximos passos possíveis (só com pedido)

1. Tratar os exames da FGV que não são concurso (CFC, ENAM, residências): esconder ou marcar.
2. Datas de inscrição da FGV a partir do edital, baixando só o PDF de abertura no Actions.
3. Aviso por e-mail pelo Actions (diferença entre o JSON novo e o anterior).
4. Outras bancas (Vunesp, FCC, Cesgranrio…).
