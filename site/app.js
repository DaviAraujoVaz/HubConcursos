// ConcursoHub: lê dados/concursos.json (gerado por concursohub.coletar) e filtra no navegador.
"use strict";

const SITUACOES = { aberto: "Inscrições abertas", previsto: "Previsto", andamento: "Em andamento", encerrado: "Encerrado" };
const ESFERAS = { federal: "Federal", estadual: "Estadual", distrital: "Distrital", municipal: "Municipal" };
const BANCAS = { cebraspe: "Cebraspe", fgv: "FGV" };
const TIPOS = {
  edital_abertura: "Edital de abertura", retificacao: "Retificação", comunicado: "Comunicado",
  inscritos: "Inscritos / demanda", gabarito: "Gabarito", resultado: "Resultado", convocacao: "Convocação",
  homologacao: "Homologação", prorrogacao: "Prorrogação", outro: "Documento",
};
const DIAS_NOVIDADE = 7;
const DIA_MS = 24 * 60 * 60 * 1000;

const fmtData = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", timeZone: "America/Sao_Paulo" });
const fmtDataHora = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo",
});
const fmtHora = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo" });
const fmtReais = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

const $ = (id) => document.getElementById(id);
const agora = new Date();
let concursos = [];
const estado = { situacao: "todos", busca: "", banca: "", esfera: "", areas: new Set(), novos: false };

function normalizar(texto) {
  return (texto || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function el(tag, attrs = {}, ...filhos) {
  const no = document.createElement(tag);
  for (const [chave, valor] of Object.entries(attrs)) {
    if (valor === null || valor === undefined || valor === false) continue;
    if (chave === "class") no.className = valor;
    else no.setAttribute(chave, valor);
  }
  for (const filho of filhos.flat()) {
    if (filho !== null && filho !== undefined && filho !== false) no.append(filho);
  }
  return no;
}

// Inscrições abertas pela situação informada ou pelo período de inscrição.
function inscricoesAbertas(c) {
  const inicio = c.inscricoes_inicio && new Date(c.inscricoes_inicio);
  const fim = c.inscricoes_fim && new Date(c.inscricoes_fim);
  if (fim && fim < agora) return false;
  if (c.situacao === "aberto") return true;
  return Boolean(inicio && fim && inicio <= agora && agora <= fim);
}

function ehNovo(c) {
  return Boolean(c.primeiro_visto) && agora - new Date(c.primeiro_visto + "T00:00:00-03:00") < DIAS_NOVIDADE * DIA_MS;
}

function preparar(c) {
  c._abertas = inscricoesAbertas(c);
  c._novo = ehNovo(c);
  c.cargos = c.cargos || [];
  c._busca = normalizar([c.titulo, ...c.cargos.map((x) => x.nome), BANCAS[c.banca], ...(c.areas || [])].join(" "));
  return c;
}

// Abertas primeiro (prazo mais curto antes), depois previstos, depois por publicação mais recente.
function ordenar(a, b) {
  if (a._abertas !== b._abertas) return a._abertas ? -1 : 1;
  if (a._abertas) return (a.inscricoes_fim || "9999").localeCompare(b.inscricoes_fim || "9999");
  const pa = a.situacao === "previsto", pb = b.situacao === "previsto";
  if (pa !== pb) return pa ? -1 : 1;
  return (b.ultima_publicacao || "").localeCompare(a.ultima_publicacao || "");
}

function casaSituacao(c, situacao) {
  if (situacao === "todos") return true;
  if (situacao === "abertas") return c._abertas;
  return !c._abertas && c.situacao === situacao;
}

function filtrados(ignorarSituacao = false) {
  const termos = normalizar(estado.busca).split(/\s+/).filter(Boolean);
  return concursos.filter((c) =>
    (ignorarSituacao || casaSituacao(c, estado.situacao)) &&
    (!estado.banca || c.banca === estado.banca) &&
    (!estado.esfera || c.esfera === estado.esfera) &&
    (!estado.novos || c._novo) &&
    (estado.areas.size === 0 || (c.areas || []).some((a) => estado.areas.has(a))) &&
    termos.every((t) => c._busca.includes(t))
  );
}

function linhaPrazo(c) {
  if (!c.inscricoes_fim) return null;
  const fim = new Date(c.inscricoes_fim);
  const inicio = c.inscricoes_inicio && new Date(c.inscricoes_inicio);
  if (fim < agora) return el("p", { class: "prazo" }, `Inscrições encerradas em ${fmtData.format(fim)}`);
  if (inicio && inicio > agora) {
    return el("p", { class: "prazo" }, "Inscrições de ", el("strong", {}, fmtData.format(inicio)), " a ", el("strong", {}, fmtData.format(fim)));
  }
  const dias = Math.ceil((fim - agora) / DIA_MS);
  const falta = dias <= 1 ? (fim.toDateString() === agora.toDateString() ? "termina hoje" : "termina amanhã") : `faltam ${dias} dias`;
  return el("p", { class: "prazo" + (dias <= 3 ? " urgente" : "") },
    "Inscrições até ", el("strong", {}, `${fmtData.format(fim)} às ${fmtHora.format(fim)}`), ` · ${falta}`);
}

function cartao(c) {
  const situacao = c._abertas ? "aberto" : c.situacao;
  const selos = el("div", { class: "selos" },
    el("span", { class: `selo ${situacao}` }, SITUACOES[situacao] || situacao),
    c._novo && el("span", { class: "selo novo" }, "novo"),
    el("span", { class: "selo banca" }, BANCAS[c.banca] || c.banca),
    c.esfera && el("span", { class: "selo" }, ESFERAS[c.esfera]),
    (c.areas || []).map((a) => el("span", { class: "selo" }, a)),
  );

  const meta = el("p", { class: "meta" },
    c.vagas > 0 && el("span", {}, `${c.vagas.toLocaleString("pt-BR")} ${c.vagas === 1 ? "vaga" : "vagas"}`),
    faixaSalarial(c) && el("span", {}, faixaSalarial(c)),
    c.ultima_publicacao && el("span", {}, `última publicação em ${fmtData.format(new Date(c.ultima_publicacao))}`),
  );

  return el("li", { class: "cartao" },
    selos,
    el("h2", {}, el("a", { href: c.url, target: "_blank", rel: "noopener" }, c.titulo)),
    linhaPrazo(c),
    meta,
    blocoCargos(c),
    blocoDocumentos(c),
  );
}

function faixaSalarial(c) {
  const salarios = c.cargos.map((x) => x.remuneracao).filter((v) => v > 0);
  if (salarios.length === 0) return c.remuneracao_maxima > 0 ? `até ${fmtReais.format(c.remuneracao_maxima)}` : "";
  const menor = Math.min(...salarios), maior = Math.max(...salarios);
  return menor === maior ? fmtReais.format(maior) : `${fmtReais.format(menor)} a ${fmtReais.format(maior)}`;
}

function linhaCargo(cargo) {
  return el("li", {},
    el("span", {}, cargo.nome),
    el("span", { class: "salario" }, cargo.remuneracao > 0 ? fmtReais.format(cargo.remuneracao) : "—"));
}

// Com área filtrada, os cargos daquela área aparecem logo no cartão; os demais ficam na lista completa.
function blocoCargos(c) {
  if (c.cargos.length === 0) return null;
  const daArea = estado.areas.size > 0 ? c.cargos.filter((x) => x.areas.some((a) => estado.areas.has(a))) : [];
  const destaque = daArea.length > 0 && daArea.length < c.cargos.length && el("div", { class: "destaque" },
    el("p", {}, `${daArea.length} ${daArea.length === 1 ? "cargo" : "cargos"} em ${[...estado.areas].join(", ")}:`),
    el("ul", { class: "cargos" }, daArea.slice(0, 6).map(linhaCargo)),
    daArea.length > 6 && el("p", { class: "mais" }, `e mais ${daArea.length - 6} na lista completa`));
  return el("div", {},
    destaque,
    el("details", {},
      el("summary", {}, `${c.cargos.length === 1 ? "Cargo e salário" : `Cargos e salários (${c.cargos.length})`}`),
      el("ul", { class: "cargos" }, c.cargos.map(linhaCargo))));
}

function blocoDocumentos(c) {
  const docs = c.documentos || [];
  return docs.length > 0 && el("details", {},
    el("summary", {}, `Documentos recentes (${c.total_documentos})`),
    el("ul", { class: "docs" },
      docs.map((d) => el("li", {},
        el("time", { datetime: d.data }, d.data ? fmtData.format(new Date(d.data + "T12:00:00-03:00")) : ""),
        el("span", {}, el("span", { class: "tipo" }, TIPOS[d.tipo] || "Documento"),
          el("a", { href: d.url, target: "_blank", rel: "noopener" }, d.titulo))))),
    c.total_documentos > docs.length && el("p", {},
      el("a", { href: c.url, target: "_blank", rel: "noopener" }, "Ver todos na página oficial")),
  );
}

function desenhar() {
  const lista = filtrados().sort(ordenar);
  $("lista").replaceChildren(...lista.map(cartao));
  $("vazio").hidden = lista.length > 0;
  $("contagem").textContent = `${lista.length} ${lista.length === 1 ? "concurso" : "concursos"}`;

  // Contagem por aba considerando os outros filtros.
  const base = filtrados(true);
  for (const botao of document.querySelectorAll(".abas button")) {
    const situacao = botao.dataset.situacao;
    botao.setAttribute("aria-pressed", String(situacao === estado.situacao));
    botao.querySelector("span").textContent = base.filter((c) => casaSituacao(c, situacao)).length;
  }
  for (const botao of document.querySelectorAll(".areas button")) {
    botao.setAttribute("aria-pressed", String(estado.areas.has(botao.dataset.area)));
  }
  salvarNaUrl();
}

// Filtros ficam na URL, para dar para salvar nos favoritos ("TI federal com inscrições abertas").
function salvarNaUrl() {
  const p = new URLSearchParams();
  if (estado.situacao !== "todos") p.set("situacao", estado.situacao);
  if (estado.busca) p.set("q", estado.busca);
  if (estado.banca) p.set("banca", estado.banca);
  if (estado.esfera) p.set("esfera", estado.esfera);
  if (estado.areas.size) p.set("areas", [...estado.areas].join(","));
  if (estado.novos) p.set("novos", "1");
  const consulta = p.toString();
  history.replaceState(null, "", consulta ? `?${consulta}` : location.pathname);
}

function lerDaUrl() {
  const p = new URLSearchParams(location.search);
  estado.situacao = p.get("situacao") || "todos";
  estado.busca = p.get("q") || "";
  estado.banca = p.get("banca") || "";
  estado.esfera = p.get("esfera") || "";
  estado.areas = new Set((p.get("areas") || "").split(",").filter(Boolean));
  estado.novos = p.get("novos") === "1";
  $("busca").value = estado.busca;
  $("banca").value = estado.banca;
  $("esfera").value = estado.esfera;
  $("novos").checked = estado.novos;
}

function montarAreas() {
  const todas = [...new Set(concursos.flatMap((c) => c.areas || []))].sort((a, b) => a.localeCompare(b, "pt-BR"));
  $("areas").replaceChildren(...todas.map((area) =>
    el("button", { type: "button", "data-area": area, "aria-pressed": "false" }, area)));
}

function ligarEventos() {
  document.querySelector(".abas").addEventListener("click", (e) => {
    const botao = e.target.closest("button");
    if (!botao) return;
    estado.situacao = botao.dataset.situacao;
    desenhar();
  });
  $("areas").addEventListener("click", (e) => {
    const botao = e.target.closest("button");
    if (!botao) return;
    const area = botao.dataset.area;
    if (estado.areas.has(area)) estado.areas.delete(area);
    else estado.areas.add(area);
    desenhar();
  });
  $("busca").addEventListener("input", (e) => { estado.busca = e.target.value.trim(); desenhar(); });
  $("banca").addEventListener("change", (e) => { estado.banca = e.target.value; desenhar(); });
  $("esfera").addEventListener("change", (e) => { estado.esfera = e.target.value; desenhar(); });
  $("novos").addEventListener("change", (e) => { estado.novos = e.target.checked; desenhar(); });
}

function mostrarStatus(status) {
  const rodape = $("status");
  if (!status || !status.gerado_em) {
    rodape.textContent = "";
    return;
  }
  const fontes = Object.entries(status.fontes || {}).map(([slug, f]) =>
    el("span", { class: f.ok ? "" : "erro", title: f.erro || "" },
      `${BANCAS[slug] || slug}: ${f.ok ? `${f.concursos} concursos` : "falhou na última coleta (mostrando dados anteriores)"}`));
  rodape.replaceChildren(`Atualizado em ${fmtDataHora.format(new Date(status.gerado_em))}. `,
    ...fontes.flatMap((f, i) => (i ? [" · ", f] : [f])));
}

async function iniciar() {
  try {
    const resposta = await fetch("dados/concursos.json", { cache: "no-cache" });
    if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
    concursos = (await resposta.json()).concursos.map(preparar);
  } catch (erro) {
    $("status").textContent = `Não foi possível carregar os concursos (${erro.message}).`;
    return;
  }
  montarAreas();
  lerDaUrl();
  ligarEventos();
  desenhar();
  fetch("dados/status.json", { cache: "no-cache" })
    .then((r) => (r.ok ? r.json() : null))
    .then(mostrarStatus)
    .catch(() => mostrarStatus(null));
}

iniciar();
