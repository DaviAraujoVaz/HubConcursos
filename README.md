# ConcursoHub

Site pessoal para consultar os concursos da **Cebraspe** e da **FGV**: quais estão com inscrições abertas, previstos ou em andamento, com filtros por **área de atuação**, **esfera** e banca, e links para os documentos oficiais.

Não precisa de servidor nem banco de dados, e não custa nada:

```
GitHub Actions (a cada 6 h)  →  coleta as bancas  →  site/dados/concursos.json  →  GitHub Pages (site estático)
```

- **Coleta:** um script Python lê a API da Cebraspe e as páginas da FGV, classifica cada concurso (área, esfera, tipo de documento) e grava um JSON.
- **Site:** HTML e JavaScript puros, que leem o JSON e filtram no navegador. Funciona no celular, e os filtros ficam na URL, então dá para salvar nos favoritos uma busca como "TI, federal, inscrições abertas".
- **Histórico:** o `concursos.json` fica no Git e só muda quando algo muda, então o histórico de commits mostra o que apareceu em cada coleta.

## Usando

Abra o site publicado no GitHub Pages: https://daviaraujovaz.github.io/HubConcursos/

- **Abas:** Todos, Inscrições abertas, Previstos, Em andamento. Inscrições abertas vêm primeiro, das que terminam antes para as que terminam depois.
- **Selo "novo":** o concurso apareceu nos últimos 7 dias. O que já existia na primeira coleta não recebe o selo.
- **Rodapé:** quando foi a última coleta e se alguma banca falhou. Se uma banca falhar, o site continua mostrando os dados anteriores dela, e o GitHub te avisa por e-mail que a execução falhou.

Para coletar na hora, sem esperar as 6 h: aba **Actions** do repositório → **Coletar e publicar** → **Run workflow**.

## Rodando no seu computador

Pré-requisito: Python 3.13.

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # no Linux/macOS: .venv/bin/pip
.venv/Scripts/python -m concursohub.coletar       # leva uns 5 minutos (1 s entre requisições)
.venv/Scripts/python -m http.server -d site 8000  # abra http://localhost:8000
.venv/Scripts/python -m unittest                  # testes; nenhum acessa a internet
```

Coletar só uma banca: `python -m concursohub.coletar cebraspe`. As outras ficam como estavam.

## Como está organizado

| Caminho | O que tem |
| --- | --- |
| `concursohub/adaptadores/` | Um arquivo por banca: `cebraspe.py` (API JSON) e `fgv.py` (HTML). Só extraem dados, não classificam nem gravam |
| `concursohub/coletar.py` | Roda os adaptadores, classifica e grava `site/dados/concursos.json` e `status.json` |
| `concursohub/areas.py` | Áreas de atuação e as palavras que levam a cada uma |
| `concursohub/inferencia.py` | Esfera a partir do título |
| `concursohub/classificador.py` | Tipo de documento (edital, retificação, resultado…) |
| `concursohub/http.py` | Cliente educado: identifica o robô, espera 1 s entre requisições e tenta de novo |
| `site/` | O site: `index.html`, `app.js`, `estilo.css` e os dados |
| `tests/` | Testes com respostas reais de cada banca |
| `.github/workflows/coletar.yml` | Coleta a cada 6 h e publica no Pages |

**De onde vêm os dados** (mapeado em 29/10/2026):

- **Cebraspe:** a API JSON que o próprio site usa (`apis.cebraspe.org.br/cebraspe/eventos/...`). Traz cargos, total de vagas, salário máximo, período de inscrição e os PDFs.
- **FGV:** o HTML de `conhecimento.fgv.br/concursos` e da página de cada concurso. Traz título, situação e PDFs. Não traz cargos nem datas de inscrição, então as áreas saem do título.

## Ajustes comuns

- **Área ou esfera errada:** adicione o caso em `tests/test_classificacao.py`, ajuste a regra em `areas.py` ou `inferencia.py` e rode os testes.
- **Banca mudou o layout:** a correção fica só no adaptador dela. Salve a resposta nova em `tests/fixtures/` e atualize o teste.
- **Banca nova:** crie `concursohub/adaptadores/<banca>.py` com uma classe `@registrar` que herda de `Adaptador`. O `coletar()` dela devolve `ConcursoExtraido`. Importe o módulo em `adaptadores/__init__.py`, inclua o nome em `BANCAS` no `site/app.js` e escreva um teste com uma resposta real.

## Limites conhecidos

- **FGV:** sem cargos, vagas e datas de inscrição, porque a página não traz essas informações. Só a leitura do edital em PDF resolveria isso.
- **A lista da FGV inclui exames que não são concurso** (Exame de Suficiência do CFC, ENAM, residências).
- **Só concursos ativos:** os encerrados saem do site quando a banca os tira da lista de ativos.
- **IPs do GitHub:** se uma banca bloquear os IPs do GitHub, a coleta pode rodar no seu computador e você faz o push do `concursos.json`.

## Versão anterior

Até 02/11/2026 o projeto era um painel em Django com banco de dados, download e leitura dos PDFs, resumo diário por e-mail e base para estatísticas. Para ter um MVP gratuito e sem servidor, essa versão foi guardada na tag `django-completo`:

```bash
git checkout django-completo
```
