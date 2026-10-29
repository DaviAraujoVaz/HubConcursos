# ConcursoHub

Hub pessoal de concursos públicos. Coleta automaticamente os concursos da **Cebraspe** e da **FGV** e os atos sobre concursos publicados no **Diário Oficial da União**. Organiza tudo num painel com filtros por **banca, esfera e área de atuação**, e avisa você no Telegram quando sai algo que interessa.

Toda informação aponta para o documento oficial de onde saiu, e cada arquivo baixado fica guardado sem alteração.

---

## Rodando pela primeira vez

Pré-requisito: [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado.

```bash
# 1. Configuração
cp .env.example .env          # abra o .env e preencha (ver abaixo)

# 2. Subir banco, painel e agendador
docker compose up -d --build

# 3. Criar seu usuário do painel
docker compose exec web python manage.py createsuperuser

# 4. Primeira coleta (só concursos ativos; leva alguns minutos por causa dos PDFs)
docker compose exec web python manage.py coletar cebraspe fgv

# 5. Marcar o que já existia como lido, para não receber centenas de avisos de uma vez
docker compose exec web python manage.py avisar --silenciar-pendentes
```

Abra **http://localhost:8000** e entre com o usuário criado.

A partir daí, o serviço `agendador` roda sozinho a cada 3 horas. Ele coleta as fontes ativas (o DOU no máximo a cada 6 h) e envia os avisos.

### O que preencher no `.env`

| Variável | Para quê |
| --- | --- |
| `DJANGO_SECRET_KEY` | Qualquer texto longo e aleatório |
| `POSTGRES_PASSWORD` | Senha do banco local |
| `INLABS_EMAIL`, `INLABS_SENHA` | Conta **gratuita** em [inlabs.in.gov.br](https://inlabs.in.gov.br), para baixar o DOU. Sem isso, o DOU é pulado |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Avisos no celular (instruções no próprio `.env.example`). Sem isso, os avisos vão só para o log |
| `CALENDARIO_TOKEN` | Senha do link do calendário |

---

## Usando o painel

- **Concursos:** a lista principal. Os filtros ficam à direita: banca, esfera, área de atuação, situação, maturidade e ano, além dos atributos que você criar. Clique num concurso para ver cargos, documentos (com link para o PDF oficial) e datas.
- **Revisado:** marque depois de conferir um concurso com o edital. A partir daí a coleta só atualiza a situação e as datas de inscrição, e o resto que você corrigiu fica preservado.
- **Documentos → "vinculado a concurso: Não":** aqui aparecem os atos do DOU (autorizações, editais, homologações). Use a ação "Criar concurso a partir do documento" ou vincule a um concurso existente.
- **Filtros de alerta:** defina o que quer acompanhar, por exemplo "Cebraspe + área TI + esfera federal" ou "palavra-chave: TJ". Só eventos que casam com algum filtro geram aviso. Falhas de coleta sempre avisam.
- **Áreas de atuação:** a taxonomia e as regras de classificação são editáveis. Se ajustar as áreas de um concurso ou cargo à mão, ele não é mais reclassificado automaticamente. Para a correção valer para casos parecidos, crie uma regra e rode `python manage.py reclassificar_areas`.
- **Definições de atributo:** cadastre um campo novo (ex.: `exige_cnh`, tipo sim/não, filtrável). Ele vira filtro no painel sem mexer em código. O valor fica no campo "atributos" do concurso, como `{"exige_cnh": true}`.
- **Fontes e Execuções:** mostram a saúde de cada coletor: última execução, último sucesso e erro.

### Calendário no celular

Assine `http://localhost:8000/calendario.ics?token=SEU_TOKEN` no Google Agenda ou no app de calendário. Ele traz o último dia de inscrição dos concursos ativos e os eventos cadastrados.

> Para o celular alcançar o endereço, o painel precisa estar acessível na rede. Por padrão ele só abre no seu computador. Veja "Rodando numa VPS".

---

## Comandos úteis

```bash
docker compose exec web python manage.py coletar cebraspe            # uma fonte
docker compose exec web python manage.py coletar todas               # todas as ativas
docker compose exec web python manage.py coletar cebraspe --encerrados  # inclui histórico (centenas de concursos)
docker compose exec web python manage.py coletar cebraspe --apenas CGU_26_AFFC PF_25
docker compose exec web python manage.py coletar fgv --sem-arquivos   # só links, sem baixar PDFs
docker compose exec web python manage.py coletar dou --de 2026-10-01 --ate 2026-10-29 --secoes DO1,DO3
docker compose exec web python manage.py avisar
docker compose exec web python manage.py reclassificar_areas
docker compose exec web python manage.py test                        # 33 testes
docker compose logs -f agendador                                     # acompanhar a coleta automática
```

---

## Como funciona

```
fonte (API / HTML / XML)  →  adaptador  →  persistência  →  catálogo  →  eventos  →  avisos / calendário
                                               │
                                               └→ dados/bruto/ (arquivos originais, nomeados pelo hash)
```

| Pasta | O que tem |
| --- | --- |
| `catalogo/` | Modelos (órgão, banca, concurso, cargo, vaga, etapa, evento, estatística), áreas de atuação, inferência de esfera, painel, calendário |
| `ingestao/adaptadores/` | Um arquivo por fonte: `cebraspe.py`, `fgv.py`, `dou.py` |
| `ingestao/persistencia.py` | Grava qualquer fonte no catálogo, sem duplicar, e emite eventos |
| `ingestao/classificador.py` | Regras que reconhecem o tipo de ato (edital, retificação, resultado…) |
| `ingestao/avisos.py` | Transforma eventos em avisos, segundo os filtros de alerta |
| `ingestao/tests/` | Testes com respostas reais e de exemplo de cada fonte, sem acessar a internet |

**De onde vem cada fonte** (mapeado em 29/10/2026):

- **Cebraspe:** a API JSON que o próprio site usa (`apis.cebraspe.org.br/cebraspe/eventos/...`). Traz cargos, vagas totais, salário máximo, período de inscrição e todos os PDFs.
- **FGV:** o HTML de `conhecimento.fgv.br/concursos` e das páginas de cada concurso. Traz título, situação e PDFs. Os cargos não estão estruturados na página, então as áreas vêm do título.
- **DOU:** os ZIPs diários do INLABS, como no [script oficial da Imprensa Nacional](https://github.com/Imprensa-Nacional/inlabs). Só entram matérias que falam de concurso ou processo seletivo.

### Adicionando uma banca nova

1. Crie `ingestao/adaptadores/<banca>.py` com uma classe `@registrar` que herda de `Adaptador` e implementa `coletar()`. O método devolve `ConcursoExtraido` com `DocumentoExtraido` e não toca no banco (use `cebraspe.py` como modelo).
2. Importe o módulo em `ingestao/adaptadores/__init__.py`.
3. Cadastre a banca no painel (Bancas) e a fonte (Fontes) com o mesmo slug.
4. Salve uma resposta real em `ingestao/tests/fixtures/` e escreva um teste.

Persistência, eventos, avisos, filtros e calendário funcionam sem mudança.

---

## Limites conhecidos e próximos passos

- **DOU:** o leitor de XML segue o formato do INLABS, mas só pôde ser testado com XML de exemplo, porque o download exige login. Na primeira coleta real, confira em Documentos se os atos chegaram bem. Os atos do DOU ainda não são vinculados sozinhos aos concursos das bancas; por ora isso é feito no painel.
- **Vagas por cargo, localidade e cota:** a Cebraspe só informa o total. O detalhamento está no PDF do edital (texto já extraído em `Documento.texto`), e extraí-lo é o próximo passo natural.
- **Datas do cronograma:** a API da Cebraspe expõe "aplicativos" com datas (consultas, recursos), que podem virar `Evento` no calendário.
- **Estatísticas** (candidatos por vaga, nota de corte): o modelo `Estatistica` está pronto. Falta o extrator dos PDFs de demanda e de resultado final.
- **PDF escaneado:** fica marcado como "precisa revisão". O ponto para plugar OCR (Tesseract) é `ingestao/pdf.py`.

## Rodando numa VPS

O mesmo `docker compose up -d` funciona numa VPS pequena, e a coleta segue mesmo com seu computador desligado. Antes de expor à internet:

- troque `DJANGO_DEBUG=false`;
- ajuste `DJANGO_ALLOWED_HOSTS`;
- coloque um proxy com HTTPS (Caddy, por exemplo) na frente;
- remova o `127.0.0.1:` da porta no `docker-compose.yml`.
