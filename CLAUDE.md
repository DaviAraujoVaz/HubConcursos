# ConcursoHub — contexto para o Claude Code

Hub **pessoal** de concursos públicos do Davi. Por enquanto é **um único usuário, sem contas nem site público**: o "app" é o Django admin, com avisos no Telegram e calendário ICS. Abrir para outros usuários é uma fase futura; não adicione autenticação de usuários finais, SEO ou front-end público sem pedido explícito.

Código, nomes de modelos/campos, mensagens e documentação são em **português**. Mantenha assim.

## Origem e decisões já tomadas

O projeto nasceu de uma conversa no claude.ai (29/10/2026). A arquitetura completa está no doc "Hub de Concursos — Arquitetura e Estratégia de Dados": https://claude.ai/artifact/EbVWH3VX84UuHMG6nJWPbP

Decisões principais:

- **Fontes oficiais primeiro.** Diários oficiais e sites das bancas são a fonte do dado. Agregadores (PCI, blogs) servem no máximo como pista de descoberta e nunca como fonte, porque o conteúdo é protegido e frágil.
- **Toda informação tem proveniência.** Cada dado aponta para um `ingestao.Documento` (URL, data, sha256). Os arquivos brutos são **imutáveis**, salvos em `dados/bruto/<fonte>/<hash>`, para que dê para reprocessar sem baixar de novo.
- **Monólito modular.** Django + PostgreSQL em Docker; cron simples (serviço `agendador`). Fila de tarefas, busca dedicada (Meilisearch) e Next.js/PWA ficam para "quando houver usuários".
- **Fontes como plugins.** Cada banca/diário é um adaptador em `ingestao/adaptadores/`. O adaptador só devolve dataclasses (`ConcursoExtraido`, `DocumentoExtraido`) e nunca toca no banco. Gravar, deduplicar e emitir eventos fica em `ingestao/persistencia.py`, igual para todas as fontes.
- **Parâmetros extensíveis sem migração.** Os campos variáveis ficam em `atributos` (JSON). `catalogo.AtributoDefinicao` registra cada chave, e o admin cria os filtros dinamicamente (`FiltrosDinamicosMixin`).
- **Eventos de domínio** (`ingestao.EventoDominio`, padrão outbox) alimentam avisos e futuras features, sem mexer na coleta.
- **Revisão humana.** Um concurso com `revisado=True` não é sobrescrito pela coleta, que atualiza só a situação e as datas de inscrição. Áreas ajustadas à mão (`areas_manuais=True`) não são reclassificadas.
- **Oficial vs. estimado:** `catalogo.Estatistica.tipo` separa os dois. A nota de corte esperada será sempre uma faixa rotulada como estimativa.
- **LGPD:** listas de resultado têm nomes. Use-as só para agregados (corte, distribuição) e não guarde dados nominais.

## Preferências do Davi

- Bancas que mais acompanha: **FGV e Cebraspe** (já têm adaptadores). Priorize essas.
- Filtros que importam: **área de atuação** (TI, Tribunais, Fiscal, Controle, Policial…) e **esfera** (federal/estadual/distrital/municipal). São independentes: um "Analista de TI de tribunal" entra em Tribunais **e** em TI.
- Ambiente: Windows (`C:\Users\davia\ProjetosPessoais\HubConcursos`), Docker Desktop.

## Como as fontes funcionam (mapeado em 29/10/2026)

- **Cebraspe** (`ingestao/adaptadores/cebraspe.py`): usa a API JSON que o próprio site consome.
  - Lista: `https://apis.cebraspe.org.br/cebraspe/eventos/tipo/concursos/` (fases: novos, inscricoes-abertas, em-andamento, encerrado).
  - Detalhe: `https://apis.cebraspe.org.br/cebraspe/eventos/<eventoURL>` (eventoCargos, arquivosEdital, arquivosGabarito, periodoInscricao, aplicativos).
  - PDFs: `https://cdn.cebraspe.org.br/concursos/<eventoURL>/arquivos/<nomeArquivo>`. Cada arquivo também vem numa versão `.html` (VLibras), que é ignorada.
- **FGV** (`fgv.py`): HTML de Drupal. Lista em `conhecimento.fgv.br/concursos?page=N` (`.view-id-concursos_em_andamento` / `concursos_realizados`). No detalhe, o título está em `<h1>`, a situação em `.field--name-field-concurso-status` e os arquivos em `.paragraph--type--texto-data`. A página não estrutura os cargos, então as áreas saem do título.
- **DOU** (`dou.py`): ZIP diário por seção via INLABS (conta gratuita; `INLABS_EMAIL`/`INLABS_SENHA`), seguindo o script oficial `github.com/Imprensa-Nacional/inlabs`. Só entram matérias que falam de concurso ou processo seletivo, e elas chegam sem concurso vinculado; o vínculo é feito no admin. **O parser só foi testado com XML de exemplo**: valide com dados reais na primeira coleta.

## Estrutura

```
config/                  settings (tudo via env; sem DATABASE_URL usa SQLite)
catalogo/                Orgao, Banca, AreaAtuacao, RegraArea, Concurso, Cargo, Vaga, Etapa, Evento,
                         Estatistica, AtributoDefinicao, FiltroAlerta; admin (a interface), calendário ICS
  classificacao.py       áreas por regras (palavra inteira; "*" no fim = prefixo)
  inferencia.py          esfera inferida do título quando não há órgão vinculado
  migrations/0003_…      bancas e taxonomia/regras de área iniciais
ingestao/                Fonte, Documento, Execucao, EventoDominio
  adaptadores/           base.py (interface + REGISTRO), cebraspe.py, fgv.py, dou.py
  persistencia.py        grava qualquer fonte, idempotente; baixa PDFs e extrai texto
  classificador.py       tipo do ato (edital, retificação, resultado, homologação…); a ordem das regras importa
  coleta.py              executa um adaptador e registra Execucao/saúde da Fonte
  avisos.py              EventoDominio → Telegram/log, conforme FiltroAlerta
  management/commands/   coletar, avisar, rotina (o que o cron roda), reclassificar_areas
  tests/                 fixtures reais/fiéis por fonte; nenhum teste acessa a internet
```

## Comandos

```bash
python manage.py test                       # 33 testes; rodar sempre antes de concluir
python manage.py coletar cebraspe fgv       # ou: todas | --encerrados | --apenas CGU_26_AFFC | --sem-arquivos
python manage.py coletar dou --de 2026-10-01 --ate 2026-10-29 --secoes DO1,DO3
python manage.py avisar [--silenciar-pendentes]
python manage.py rotina
docker compose up -d --build
docker compose exec web python manage.py test
```

## Convenções ao mexer no código

- **Nova fonte:** crie o adaptador com `@registrar`, importe em `adaptadores/__init__.py`, salve uma resposta real em `tests/fixtures/` e escreva um teste. Não mexa na persistência por causa de uma fonte.
- **Site mudou de layout:** a correção fica só no adaptador daquela fonte. Atualize a fixture com a resposta nova.
- **Classificação errada** (tipo de ato ou área): adicione um caso ao teste correspondente antes de ajustar a regra. Casos reais já cobertos: "Edital (retificado em…)" é edital de abertura, não retificação; "Comunicado – … resultado…" é comunicado.
- **Coleta educada:** `ingestao/http.py` identifica o robô, espera entre requisições e tenta de novo. Use sempre esse cliente.
- Testes de fonte usam `ClienteFalso` (`ingestao/tests/util.py`) e `TesteComDados`, que isola `DADOS_DIR`.

## Estado atual e próximos passos sugeridos

Feito: modelos, admin com filtros (banca, esfera, área, atributos dinâmicos), coletores Cebraspe/FGV/DOU, avisos, calendário, Docker. Nenhuma coleta ao vivo foi rodada ainda: a primeira será na máquina do Davi.

Próximos passos, em ordem de valor:

1. **Primeira coleta real** de Cebraspe e FGV, e conferência dos resultados no admin.
2. **Extrair do texto do edital** (`Documento.texto`): vagas por cargo/localidade/cota, remuneração por cargo, escolaridade e cronograma (→ `Evento`). A Cebraspe só informa o total de vagas.
3. **Eventos a partir de `aplicativos` da Cebraspe** (datas de consultas e recursos) → calendário.
4. **Estatísticas:** extrair candidatos por vaga dos PDFs de demanda e notas de corte dos resultados finais. Depois, a nota de corte esperada (base histórica e, mais tarde, regressão quantílica).
5. **Vincular atos do DOU** a concursos existentes (órgão + cargo + ano).
6. **OCR** (Tesseract) em `ingestao/pdf.py` para PDFs escaneados (`precisa_revisao=True`).
7. Outras bancas e Querido Diário (municípios), conforme o interesse do Davi.
