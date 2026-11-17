// ---------- Optimizer da Wheel of Destiny (submenu do menu Wheel of Destiny) ----------
// A tela monta o pedido (vocação, pontos, obrigatórios, opcionais em ordem, metas dos pontos extras), manda para o worker
// (otimizador_worker.js + otimizador_motor.js, com o resolvedor HiGHS) e desenha a melhor roda, as variantes, o resumo e
// quantos pontos faltam para as próximas metas. O resultado vira código W26 para abrir no Planner ou salvar nas minhas rodas.
// Usa do index.html/roda.js: $, esc, api, toast, MEUS, carregarRodas, abrirRodaNoPlanner.
const OTM = { dados: null, voc: 'sorcerer', pedidos: {}, res: null, variante: 0, worker: null, seq: 0, espera: new Map(), fatia: null, pn: null };
const OTM_VOCS = [['knight', 'Knight'], ['paladin', 'Paladin'], ['sorcerer', 'Sorcerer'], ['druid', 'Druid'], ['monk', 'Monk']];
const OTM_STATS = { hp: 'HP', mana: 'Mana', capacity: 'Capacity', mitigation: 'Mitigação' };
const OTM_ROMANO = ['—', 'I', 'II', 'III'];
const OTM_TIPOS = { spellAugment: 'Augments de magia', passive: 'Passivos', skill: 'Skills', leech: 'Leech', revelationMastery: 'Revelation Mastery', gemVessel: 'Gem Vessel' };
const OTM_CORES = { obrigatorio: '#f5b301', opcional: '#4cc38a', vessel: '#b07cff', mastery: '#39c0d6', caminho: '#7b8aa3', extra: '#e8743b' };
const OTM_PAPEIS = { obrigatorio: 'Obrigatório', opcional: 'Opcional', vessel: 'Gem Vessel', mastery: 'Revelation Mastery', caminho: 'Caminho', extra: 'Pontos extras' };

const otmVoc = () => OTM.dados.vocacoes[OTM.voc];
const otmPerk = (id) => (otmVoc().perks.find((p) => p.id === id) || { nome: id, max: 1 });
const otmDominio = (id) => (otmVoc().dominios.find((d) => d.id === id) || { revelacao: id });
const otmNovoPedido = () => ({ pontos: 500, obrigatorio: { perks: [], revelacao: {}, gemas: 0, gemasRevelacao: [] }, opcionais: [], sobras: ['gemas'] });
const otmPed = () => (OTM.pedidos[OTM.voc] ||= otmNovoPedido());
function otmGuardar() { try { localStorage.setItem('zt-otm', JSON.stringify({ voc: OTM.voc, pedidos: OTM.pedidos })); } catch (e) { /* só conveniência */ } }

async function abrirOtimizador() {
  if (!OTM.dados) {
    try { OTM.dados = await (await fetch('roda_otimizador.json')).json(); } catch (e) { $('otm').innerHTML = '<p class="dica">Não consegui ler os dados da roda.</p>'; return; }
    try { const s = JSON.parse(localStorage.getItem('zt-otm') || 'null'); if (s && OTM.dados.vocacoes[s.voc]) { OTM.voc = s.voc; OTM.pedidos = s.pedidos || {}; } } catch (e) { /* começa do zero */ }
  }
  otmDesenharForm();
  if (!OTM.res) otmCalcular();
}

// ---------- worker ----------
function otmPedirWorker(msg) {
  if (!OTM.worker) {
    OTM.worker = new Worker('otimizador_worker.js');
    OTM.worker.onmessage = (e) => { const p = OTM.espera.get(e.data.id); if (p) { OTM.espera.delete(e.data.id); e.data.ok ? p.ok(e.data.r) : p.erro(new Error(e.data.erro)); } };
    OTM.worker.onerror = (e) => { for (const p of OTM.espera.values()) p.erro(new Error(e.message || 'o worker falhou')); OTM.espera.clear(); OTM.worker = null; };
  }
  const id = ++OTM.seq;
  return new Promise((ok, erro) => { OTM.espera.set(id, { ok, erro }); OTM.worker.postMessage({ id, ...msg }); });
}

// ---------- formulário: tudo por clique (níveis em botões, disponíveis em chips, arrastar para reordenar) ----------
function otmOpcaoTexto(op) {
  if (op.tipo === 'revelacao') return `${otmDominio(op.dominio).revelacao} estágio ${OTM_ROMANO[op.estagio]}`;
  if (op.tipo === 'gemas') return `${op.n} gem slots`;
  return `${otmPerk(op.perk).nome}${op.copias > 1 ? ' ×' + op.copias : ''}`;
}
function otmMetaTexto(m) {
  if (m === 'gemas') return 'Próximo gem slot';
  if (m === 'skill') return 'Skill: próximo +1';
  if (m.startsWith('perk:')) return `${otmPerk(m.slice(5)).nome}: próxima fatia`;
  if (m.startsWith('revelacao:')) return `${otmDominio(m.slice(10)).revelacao}: próximo estágio`;
  return OTM_STATS[m] || m;
}
const otmTipoPerk = (id) => (otmVoc().fatias.find((f) => f.perk === id) || { tipo: 'passive' }).tipo;
// rótulo de cada nível: augment I/II, skill +1..+4, leech ×1..×4, passivo ✓
const otmNivelRot = (tipo, n, max) => (max === 1 ? '✓' : tipo === 'skill' ? '+' + n : tipo === 'leech' ? '×' + n : OTM_ROMANO[n] || String(n));
const otmLetra = (q) => ({ lesser: 'L', regular: 'R', greater: 'G' }[q] || '?');
const otmFaixa = (n) => Array.from({ length: n }, (_, k) => k + 1);
// fileira de botões de nível; acende do 1 até o atual
const otmBotoes = (attr, atual, niveis, rot, titulo = () => '') => `<span class="otm-niv">${niveis.map((n) =>
  `<button type="button" class="otm-bt${atual && n <= atual ? ' on' : ''}" ${attr(n)} title="${esc(titulo(n))}">${esc(rot(n))}</button>`).join('')}</span>`;
// botões L/R/G dos gem slots (lesser, regular, greater, na ordem em que liberam)
const otmSlots = (attr, n) => otmBotoes(attr, n, otmFaixa(8), (k) => otmLetra(otmVoc().ordem_gemas[k - 1]), (k) => `${k} gem slots (o ${k}º é ${otmVoc().ordem_gemas[k - 1]})`);
// linha de uma lista com prioridade: alça para arrastar, ↑ ↓ ✕
const otmLinhaLista = (lista, k, total, texto, meio = '') => `<div class="otm-item" data-otm-arrastar="${lista}:${k}">
  <span class="otm-alca" title="Arraste para mudar a ordem" aria-hidden="true">⠿</span><span class="otm-nome">${k + 1}. ${esc(texto)}</span>${meio}
  <span class="otm-acoes"><button type="button" class="otm-bt" data-otm-subir="${lista}:${k}" ${k ? '' : 'disabled'} title="Subir (mais prioridade)">↑</button><button type="button" class="otm-bt" data-otm-descer="${lista}:${k}" ${k < total - 1 ? '' : 'disabled'} title="Descer">↓</button><button type="button" class="otm-bt" data-otm-tirar="${lista}:${k}" title="Tirar">✕</button></span></div>`;

function otmDesenharForm() {
  const voc = otmVoc(), p = otmPed(), ob = p.obrigatorio;
  const copiasOb = (id) => (ob.perks.find((x) => x.perk === id) || {}).copias || 0;
  // perks obrigatórios por tipo (vessel tem a barra própria; a Revelation Mastery o cálculo põe sozinho quando compensa)
  const grupos = {};
  voc.perks.forEach((pk) => { const t = otmTipoPerk(pk.id); if (t !== 'gemVessel' && t !== 'revelationMastery') (grupos[t] ||= []).push(pk); });
  const blocoPerks = ['spellAugment', 'passive', 'skill', 'leech'].filter((t) => grupos[t]).map((t) => `<div class="otm-grupo"><div class="campo-label">${esc(OTM_TIPOS[t])}</div>${grupos[t].map((pk) =>
    `<div class="otm-perk"><span>${esc(pk.nome)}</span>${otmBotoes((n) => `data-otm-ob="${esc(pk.id)}:${n}"`, copiasOb(pk.id), otmFaixa(pk.max), (n) => otmNivelRot(t, n, pk.max), (n) => `Obrigatório: ${pk.nome} ${otmNivelRot(t, n, pk.max)}`)}</div>`).join('')}</div>`).join('');
  const revs = voc.dominios.map((d) => {
    const gemas = ob.gemasRevelacao.map((g, k) => (g.dominio === d.id ? `<span class="otm-gema">◆ +${voc.bonus_gema[g.grau - 1]} ${['', 'I', 'II', 'III', 'IV'][g.grau]}<button type="button" class="otm-x" data-otm-tirar="gemrev:${k}" title="Tirar a gema">✕</button></span>` : '')).join('');
    return `<div class="otm-revdom"><div class="otm-perk"><b>${esc(d.revelacao)}</b>${otmBotoes((n) => `data-otm-rev="${esc(d.id)}:${n}"`, ob.revelacao[d.id] || 0, [1, 2, 3], (n) => OTM_ROMANO[n], (n) => `Pelo menos estágio ${OTM_ROMANO[n]} (${voc.estagios[n - 1]} pontos)`)}</div>
      <div class="otm-perk"><span class="dica">+ gema</span>${otmBotoes((n) => `data-otm-gemrev="${esc(d.id)}:${n}"`, 0, [1, 2, 3, 4], (n) => '+' + voc.bonus_gema[n - 1], (n) => `Gema greater com mod de revelação, grau ${n} (+${voc.bonus_gema[n - 1]})`)}</div>${gemas ? `<div>${gemas}</div>` : ''}</div>`;
  }).join('');
  // opcionais: cada linha tem os próprios níveis; abaixo, os disponíveis para clicar
  const opcionais = p.opcionais.map((op, k) => {
    let meio = '';
    if (op.tipo === 'perk') { const pk = otmPerk(op.perk), t = otmTipoPerk(op.perk); if (pk.max > 1) meio = otmBotoes((n) => `data-otm-opcniv="${k}:${n}"`, op.copias, otmFaixa(pk.max), (n) => otmNivelRot(t, n, pk.max)); }
    else if (op.tipo === 'revelacao') meio = otmBotoes((n) => `data-otm-opcniv="${k}:${n}"`, op.estagio, [1, 2, 3], (n) => OTM_ROMANO[n]);
    else meio = otmSlots((n) => `data-otm-opcniv="${k}:${n}"`, op.n);
    const nome = op.tipo === 'perk' ? otmPerk(op.perk).nome : op.tipo === 'revelacao' ? otmDominio(op.dominio).revelacao : 'Gem slots';
    return otmLinhaLista('opc', k, p.opcionais.length, nome, meio);
  }).join('') || '<div class="otm-vazio">Nenhum opcional. Clique nos disponíveis abaixo.</div>';
  const usado = (fn) => p.opcionais.some(fn);
  const chip = (attr, texto) => `<button type="button" class="otm-bt otm-chip" ${attr}>+ ${esc(texto)}</button>`;
  const disponiveis = [
    ...voc.perks.filter((pk) => otmTipoPerk(pk.id) !== 'gemVessel' && !copiasOb(pk.id) && !usado((o) => o.tipo === 'perk' && o.perk === pk.id)).map((pk) => chip(`data-otm-opcadd="perk:${esc(pk.id)}"`, pk.nome)),
    ...voc.dominios.filter((d) => !usado((o) => o.tipo === 'revelacao' && o.dominio === d.id)).map((d) => chip(`data-otm-opcadd="rev:${esc(d.id)}"`, d.revelacao + ' (estágio)')),
    ...(usado((o) => o.tipo === 'gemas') ? [] : [chip('data-otm-opcadd="gemas"', 'Gem slots')])].join('');
  const sobras = p.sobras.map((m, k) => otmLinhaLista('sob', k, p.sobras.length, otmMetaTexto(m))).join('') || '<div class="otm-vazio">Nenhuma meta: os pontos extras vão para onde der.</div>';
  const metas = ['gemas', 'skill', ...voc.dominios.map((d) => 'revelacao:' + d.id), ...Object.keys(OTM_STATS),
    ...voc.perks.filter((x) => !['gemVessel', 'revelationMastery'].includes(otmTipoPerk(x.id))).map((x) => 'perk:' + x.id)].filter((m) => !p.sobras.includes(m));
  $('otm-form').innerHTML = `
    <div class="otm-linha">
      <span class="otm-niv">${OTM_VOCS.map(([v, n]) => `<button type="button" class="otm-bt otm-voc${v === OTM.voc ? ' on' : ''}" data-otm-voc="${v}">${n}</button>`).join('')}</span>
      <label class="otm-pontos"><span class="campo-label">Pontos</span><input type="number" id="otm-pontos" class="otm-num" min="0" max="4000" value="${p.pontos}" title="Pontos de promoção: level − 50 + pergaminhos"></label>
      <button class="btn btn-primary btn-sm" id="otm-calcular">Recalcular</button><span class="dica" id="otm-status"></span>
    </div>
    <div class="otm-sec"><h4 class="sub3">Perks obrigatórios <span class="dica">(selecionados: ${ob.perks.length})</span></h4><div class="otm-grupos">${blocoPerks}</div></div>
    <div class="otm-sec"><h4 class="sub3">Revelação e gemas</h4>
      <div class="otm-perk otm-slots"><span>Mín. de gem slots</span><input type="range" id="otm-gemas" min="0" max="8" value="${ob.gemas}"><b id="otm-gemas-n">${ob.gemas}</b>${otmSlots((n) => `data-otm-gemas="${n}"`, ob.gemas)}</div>
      <p class="dica" style="margin:6px 0">Estágios I / II / III = ${voc.estagios.join(' / ')} pontos no quadrante. O cálculo põe a Revelation Mastery (+${voc.bonus_mastery}) sozinho quando compensa. A gema de revelação só vale num slot greater liberado (3º, 5º, 7º e 8º vessel) e só é usada se precisar.</p>
      <div class="otm-revs">${revs}</div></div>
    <div class="otm-grade2">
      <div class="otm-sec"><h4 class="sub3">Opcionais: a ordem é a prioridade</h4><p class="dica" style="margin:0 0 6px">Arraste para reordenar. Um de cima vale mais que todos os de baixo juntos.</p>
        <div class="otm-lista">${opcionais}</div>
        <div class="campo-label" style="margin-top:8px">Disponíveis (não obrigatórios)</div><div class="otm-chips">${disponiveis || '<span class="dica">Nada mais para adicionar.</span>'}</div></div>
      <div class="otm-sec"><h4 class="sub3">Pontos extras: a ordem é a prioridade</h4><p class="dica" style="margin:0 0 6px">O que sobra vai primeiro para a meta de cima. "Próximo estágio" empurra a revelação até o próximo limite (ex.: 475 → 500).</p>
        <div class="otm-lista">${sobras}</div>
        <div class="campo-label" style="margin-top:8px">Disponíveis</div><div class="otm-chips">${metas.map((m) => chip(`data-otm-sobadd="${esc(m)}"`, otmMetaTexto(m))).join('')}</div></div>
    </div>`;
}

// cada mudança guarda, redesenha e recalcula sozinho (um pouco depois do último clique)
let otmTimer = null;
function otmMudou() {
  otmGuardar(); otmDesenharForm();
  clearTimeout(otmTimer);
  otmTimer = setTimeout(otmCalcular, 450);
}
const otmAlterna = (atual, n) => (atual === n ? n - 1 : n);   // clicar no nível já aceso desce um (no 1: desliga)
function otmMover(arr, de, para) { if (para < 0 || para >= arr.length || de === para) return; const [x] = arr.splice(de, 1); arr.splice(para, 0, x); }
$('otm-form').addEventListener('click', (e) => {
  const b = e.target.closest('button'); if (!b || b.disabled) return;
  const p = otmPed(), ob = p.obrigatorio, d = b.dataset;
  if (b.id === 'otm-calcular') { clearTimeout(otmTimer); otmCalcular(); return; }
  if (d.otmVoc) { if (d.otmVoc !== OTM.voc) { OTM.voc = d.otmVoc; OTM.res = null; OTM.pn = null; otmDesenharResultado(); otmMudou(); } return; }
  if (d.otmOb) {
    const [id, n0] = d.otmOb.split(':'), x = ob.perks.find((y) => y.perk === id), novo = otmAlterna(x ? x.copias : 0, +n0);
    if (!novo) ob.perks = ob.perks.filter((y) => y.perk !== id);
    else if (x) x.copias = novo; else ob.perks.push({ perk: id, copias: novo });
  } else if (d.otmRev) { const [dom, n0] = d.otmRev.split(':'), novo = otmAlterna(ob.revelacao[dom] || 0, +n0); if (novo) ob.revelacao[dom] = novo; else delete ob.revelacao[dom]; }
  else if (d.otmGemrev) {
    const [dom, n0] = d.otmGemrev.split(':');
    if (ob.gemasRevelacao.length >= 4) { toast('No máximo 4 gemas de revelação (são 4 slots greater).', true); return; }
    ob.gemasRevelacao.push({ dominio: dom, grau: +n0 });
  } else if (d.otmGemas !== undefined) ob.gemas = otmAlterna(ob.gemas, +d.otmGemas);
  else if (d.otmOpcniv) {
    const [k, n0] = d.otmOpcniv.split(':').map(Number), op = p.opcionais[k];
    if (op.tipo === 'perk') op.copias = n0; else if (op.tipo === 'revelacao') op.estagio = n0; else op.n = n0;
  } else if (d.otmOpcadd) {
    const [tipo, a] = d.otmOpcadd.split(':');
    p.opcionais.push(tipo === 'perk' ? { tipo: 'perk', perk: a, copias: otmPerk(a).max } : tipo === 'rev' ? { tipo: 'revelacao', dominio: a, estagio: 1 } : { tipo: 'gemas', n: Math.min(8, (ob.gemas || 0) + 1) });
  } else if (d.otmSobadd) p.sobras.push(d.otmSobadd);
  else {
    const [acao, alvo] = ['otmSubir', 'otmDescer', 'otmTirar'].map((k) => [k, d[k]]).find(([, v]) => v !== undefined) || [];
    if (!acao) return;
    const [lista, k0] = alvo.split(':'), k = +k0;
    const arr = lista === 'opc' ? p.opcionais : lista === 'sob' ? p.sobras : ob.gemasRevelacao;
    if (acao === 'otmTirar') arr.splice(k, 1);
    else otmMover(arr, k, acao === 'otmSubir' ? k - 1 : k + 1);
  }
  otmMudou();
});
// a barra dos gem slots: mostra o número enquanto arrasta e só aplica ao soltar (redesenhar no meio quebraria o arraste)
$('otm-form').addEventListener('input', (e) => { if (e.target.id === 'otm-gemas') $('otm-gemas-n').textContent = e.target.value; });
$('otm-form').addEventListener('change', (e) => {
  const p = otmPed();
  if (e.target.id === 'otm-gemas') p.obrigatorio.gemas = +e.target.value;
  else if (e.target.id === 'otm-pontos') p.pontos = Math.max(0, Math.min(4000, Math.floor(+e.target.value || 0)));
  else return;
  otmMudou();
});
// arrastar para reordenar (opcionais ou pontos extras), com eventos de ponteiro: funciona com mouse e toque
let otmArraste = null;
$('otm-form').addEventListener('pointerdown', (e) => {
  const it = e.target.closest('[data-otm-arrastar]');
  if (!it || e.button !== 0 || e.target.closest('button')) return;
  const [lista, k] = it.dataset.otmArrastar.split(':');
  otmArraste = { lista, k: +k, alvo: +k };
  it.classList.add('arrastando');
  it.setPointerCapture(e.pointerId);
  e.preventDefault();
});
$('otm-form').addEventListener('pointermove', (e) => {
  if (!otmArraste) return;
  const linhas = [...document.querySelectorAll(`#otm-form [data-otm-arrastar^="${otmArraste.lista}:"]`)];
  let alvo = linhas.length - 1;
  for (let i = 0; i < linhas.length; i++) { const r = linhas[i].getBoundingClientRect(); if (e.clientY < r.top + r.height / 2) { alvo = i; break; } }
  otmArraste.alvo = alvo;
  linhas.forEach((l, i) => l.classList.toggle('alvo', i === alvo && alvo !== otmArraste.k));
});
function otmSoltar() {
  if (!otmArraste) return;
  const { lista, k, alvo } = otmArraste, p = otmPed();
  otmArraste = null;
  if (alvo === k) { otmDesenharForm(); return; }
  otmMover(lista === 'opc' ? p.opcionais : p.sobras, k, alvo);
  otmMudou();
}
$('otm-form').addEventListener('pointerup', otmSoltar);
$('otm-form').addEventListener('pointercancel', otmSoltar);

// ---------- cálculo ----------
async function otmCalcular() {
  const st = $('otm-status'), btn = $('otm-calcular');
  if (st) st.textContent = 'Calculando…';
  if (btn) btn.disabled = true;
  OTM.pn = null;
  const vocacao = OTM.voc, pedido = JSON.parse(JSON.stringify(otmPed()));   // a foto do pedido: cliques durante o cálculo não misturam
  try {
    const res = await otmPedirWorker({ tipo: 'otimizar', vocacao, voc: OTM.dados.vocacoes[vocacao], pedido });
    if (vocacao !== OTM.voc) return;   // trocou de vocação no meio: o cálculo novo já vem
    OTM.res = res;
    OTM.res.vocacao = vocacao;
    OTM.res.pedido = pedido;
    OTM.variante = 0; OTM.fatia = null;
    if ($('otm-status')) $('otm-status').textContent = '';
  } catch (e) {
    OTM.res = null;
    if ($('otm-status')) $('otm-status').textContent = 'O cálculo falhou: ' + e.message;
  } finally {
    if ($('otm-calcular')) $('otm-calcular').disabled = false;   // o formulário pode ter sido redesenhado no meio
  }
  otmDesenharResultado();
}

// ---------- resultado ----------
function otmPapel(voc, fa, pts, ped) {
  if (!pts) return null;
  if (pts < fa.custo) return 'extra';
  if (fa.tipo === 'gemVessel') return 'vessel';
  if (fa.tipo === 'revelationMastery') return 'mastery';
  if (ped.obrigatorio.perks.some((x) => x.perk === fa.perk)) return 'obrigatorio';
  if (ped.opcionais.some((o) => o.tipo === 'perk' && o.perk === fa.perk)) return 'opcional';
  return 'caminho';
}
function otmRodaSVG(voc, vetor, ped) {
  const pt = (r, a) => { const t = a * Math.PI / 180; return `${(r * Math.cos(t)).toFixed(2)} ${(r * Math.sin(t)).toFixed(2)}`; };
  const setor = (ri, ro, a0, a1) => (ri < 2 ? `M 0 0 L ${pt(ro, a0)} A ${ro} ${ro} 0 0 1 ${pt(ro, a1)} Z`
    : `M ${pt(ri, a0)} L ${pt(ro, a0)} A ${ro} ${ro} 0 0 1 ${pt(ro, a1)} L ${pt(ri, a1)} A ${ri} ${ri} 0 0 0 ${pt(ri, a0)} Z`);
  const partes = voc.fatias.map((fa, i) => {
    const [ri, ro, a0, a1] = fa.geo, pts = vetor[i] || 0, papel = otmPapel(voc, fa, pts, ped);
    const cheio = papel ? `<path d="${setor(ri, ri + (ro - ri) * Math.min(1, pts / fa.custo), a0, a1)}" fill="${OTM_CORES[papel]}" fill-opacity="${pts < fa.custo ? .55 : .9}"/>` : '';
    const titulo = `${otmPerk(fa.perk).nome} · ${pts}/${fa.custo}${papel ? ' · ' + OTM_PAPEIS[papel] : ''}`;
    const [mx, my] = pt((ri + ro) / 2, (a0 + a1) / 2).split(' ');
    return `<g class="otm-fatia${OTM.fatia === i ? ' sel' : ''}" data-otm-fatia="${i}" tabindex="0" role="button" aria-label="${esc(titulo)}"><title>${esc(titulo)}</title>
      <path d="${setor(ri, ro, a0, a1)}" fill="#20242c" stroke="#0e1014" stroke-width="2"/>${cheio}
      ${pts ? `<text x="${mx}" y="${my}" text-anchor="middle" dominant-baseline="middle" class="otm-txt">${pts}</text>` : ''}</g>`;
  }).join('');
  return `<svg class="otm-svg" viewBox="-265 -265 530 530" role="group" aria-label="Roda calculada">${partes}
    <line x1="-262" y1="0" x2="262" y2="0" stroke="#0e1014" stroke-width="3"/><line x1="0" y1="-262" x2="0" y2="262" stroke="#0e1014" stroke-width="3"/></svg>`;
}
function otmDetalheFatia(voc, vetor) {
  if (OTM.fatia === null) return '<p class="dica">Clique numa fatia da roda para ver os detalhes.</p>';
  const fa = voc.fatias[OTM.fatia], pts = vetor[OTM.fatia] || 0;
  const ded = Object.entries(fa.dedicacao).map(([s, v]) => `${OTM_STATS[s]} +${+(v * pts).toFixed(3)}`).join(' · ');
  return `<p><b>${esc(otmPerk(fa.perk).nome)}</b> <span class="dica">(${esc(OTM_TIPOS[fa.tipo] || fa.tipo)})</span><br>${pts} / ${fa.custo} pontos
    <br><span class="dica">Dedicação:</span> ${esc(ded || '—')}<br><span class="dica">Convicção:</span> ${pts >= fa.custo ? 'ativa' : 'inativa (a fatia não está cheia)'}</p>`;
}
function otmResumo(voc, r, ped) {
  const rev = r.revelacao.map((x) => `<tr><td>${esc(x.nome)}</td><td class="r">${x.progresso}</td><td class="r">${x.estagio ? 'estágio ' + OTM_ROMANO[x.estagio] : 'sem estágio'}</td></tr>`).join('');
  const opc = r.opcionais.map((o) => `<li>${o.ok ? '✔' : '✘'} ${esc(otmOpcaoTexto(o))} <span class="dica">(${o.feito})</span></li>`).join('') || '<li class="dica">Nenhum opcional escolhido.</li>';
  const ded = Object.entries(OTM_STATS).map(([s, n]) => `<tr><td>${n}</td><td class="r">+${s === 'mitigation' ? r.dedicacao[s].toFixed(2) + '%' : Math.round(r.dedicacao[s])}</td></tr>`).join('');
  const gemas = r.gemasRevelacao.filter((g) => !g.encaixada).map((g) => `<p class="dica">Gema +${g.bonus} (${esc(otmDominio(g.dominio).revelacao)}) não foi usada: sem ela tudo já fecha, então o slot greater fica livre para outra gema.</p>`).join('');
  return `<div class="otm-resumo">
    <div><b>${r.gasto}</b> gastos · <b>${r.livres}</b> livres${r.minimoObrigatorio !== null ? ` · obrigatórios custam ${r.minimoObrigatorio}` : ''}</div>
    <div class="tabela-wrap"><table class="tab"><tr><th>Revelação</th><th class="r">Progresso</th><th class="r">Estágio</th></tr>${rev}</table></div>
    <div>Gem slots: <b>${r.vessels}</b> de 8 ${r.slots.length ? `<span class="dica">(${esc(r.slots.join(', '))})</span>` : ''} · +${r.danoCura} dano/cura dos vessels</div>${gemas}
    <h4 class="sub3">Opcionais</h4><ul class="otm-ul">${opc}</ul>
    <h4 class="sub3">Dedicação</h4><div class="tabela-wrap"><table class="tab">${ded}</table></div></div>`;
}
function otmDesenharResultado() {
  const alvo = $('otm-res'), r = OTM.res;
  if (!r) { alvo.innerHTML = ''; return; }
  const voc = OTM.dados.vocacoes[r.vocacao], ped = r.pedido;
  let cab = '', roda = null;
  if (r.status === 'nao_cabe') {
    const conf = r.conflitos.map((c) => `<li>${esc(c.tipo === 'perk' ? otmPerk(c.perk).nome + (c.copias > 1 ? ' ×' + c.copias : '') : c.tipo === 'revelacao' ? otmDominio(c.dominio).revelacao + ' estágio ' + OTM_ROMANO[c.estagio] : c.n + ' gem vessels')}:
      ${c.minimoSem === null ? 'continua impossível sem ele' : r.minimo === null ? `sem ele dá a partir de ${c.minimoSem} pontos` : `sem ele: ${c.minimoSem} pontos (−${c.economia})`}</li>`).join('');
    cab = `<div class="otm-aviso"><b>Os obrigatórios não cabem.</b> ${r.motivo === 'impossivel' ? 'Eles se excluem com qualquer número de pontos.' : `Precisa de ${r.minimo} pontos: faltam ${r.faltam}.`}
      ${conf ? `<div class="dica" style="margin-top:6px">O que mais pesa:</div><ul class="otm-ul">${conf}</ul>` : ''}</div>`;
    if (r.noMinimo) { roda = r.noMinimo; cab += `<p class="dica">A roda abaixo é a mais barata que cumpre os obrigatórios: ${r.minimo} pontos.</p>`; }
  } else roda = r.variantes[OTM.variante] || r;
  if (!roda) { alvo.innerHTML = cab; return; }
  const abas = r.status === 'ok' && r.variantes.length > 1 ? `<div class="abas" style="margin:0 0 8px">${r.variantes.map((_, k) => `<span class="pilula ${k === OTM.variante ? 'on' : ''}" data-otm-var="${k}">Variante ${k + 1}</span>`).join('')}</div>`
    : r.status === 'ok' ? '<p class="dica" style="margin:0 0 8px">Só existe um jeito de montar a roda com esse resultado.</p>' : '';
  const legenda = Object.entries(OTM_PAPEIS).map(([k, n]) => `<span class="otm-leg"><i style="background:${OTM_CORES[k]}"></i>${n}</span>`).join('');
  const ordem = roda.ordem.map((o, k) => `<li>${esc(otmPerk(voc.fatias.find((f) => f.id === o.fatia).perk).nome)} <span class="dica">${o.pontos} pts</span></li>`).join('');
  alvo.innerHTML = `${cab}${abas}
    <div class="otm-grade">
      <div><div class="dica"><b>${roda.gasto}</b> de ${r.status === 'ok' ? ped.pontos : r.minimo} pontos · ${esc(OTM_VOCS.find(([v]) => v === r.vocacao)[1])} · passe o mouse nas fatias para ver o perk</div>
        <div id="otm-roda-vista"></div></div>
      <div>${otmResumo(voc, roda, ped)}</div>
    </div>
    <div class="roda-barra">
      <button class="btn btn-sm btn-primary" id="otm-planner" title="Abre esta roda no Planner (aba ao lado), com o código W26">🛞 Abrir no Planner</button>
      <input type="text" id="otm-nome" placeholder="Nome da roda" maxlength="60">
      <button class="btn btn-sm" id="otm-salvar">💾 Salvar nas minhas rodas</button>
      <button class="btn btn-sm" id="otm-copiar" title="Copia o código W26">Copiar código</button>
    </div>
    <details class="otm-det"><summary>Ordem para clicar no jogo (${roda.ordem.length} fatias)</summary><ol class="otm-ul">${ordem}</ol></details>
    <details class="otm-det" id="otm-pn-det" ${OTM.pnAberto ? 'open' : ''}><summary>Pontos necessários para as próximas metas</summary><div id="otm-pn">${otmPnHtml()}</div></details>`;
  // a roda do update, com as imagens, é o próprio planner novo só com o desenho; sem internet cai nas fatias coloridas
  const vista = $('otm-roda-vista');
  mostrarRoda(vista, roda.codigo, { nova: true, soRoda: true, aoResumo: () => {} }).then((ok) => {
    if (!ok && vista.isConnected) vista.innerHTML = `<div class="otm-roda">${otmRodaSVG(voc, roda.vetor, ped)}</div><div class="otm-legenda">${legenda}</div>
      <div id="otm-fatia-info">${otmDetalheFatia(voc, roda.vetor)}</div>`;
  });
}
function otmPnHtml() {
  const pn = OTM.pn;
  if (!pn) return '<p class="dica">Calculando ao abrir…</p>';
  if (pn.erro) return `<p class="dica">${esc(pn.erro)}</p>`;
  const f = (x) => (x === null ? '<span class="dica">impossível</span>' : x === 0 ? '✔ cabe agora' : `faltam ${x}`);
  const gem = pn.gemas.map((g) => `<tr><td>${g.slots} <span class="dica">(${esc(g.qualidade || '')})</span></td><td class="r">${g.minimo ?? '—'}</td><td class="r">${f(g.faltam)}</td></tr>`).join('');
  const opc = pn.opcionais.map((o, k) => `<tr><td>${k + 1}. ${esc(otmOpcaoTexto(o))}</td><td class="r">${o.minimo ?? '—'}</td><td class="r">${f(o.faltam)}</td><td class="r">${o.sozinho === null ? '—' : o.sozinho}</td></tr>`).join('');
  const rev = pn.revelacao.map((x) => `<tr><td>${esc(x.nome)} estágio ${OTM_ROMANO[x.estagio]}</td><td class="r">${x.minimo ?? '—'}</td><td class="r">${f(x.faltam)}</td>
    <td>${x.comGemas.map((g) => `com ${g.gemas} gema${g.gemas > 1 ? 's' : ''} (+${g.bonus}): ${g.minimo}`).join('<br>') || '—'}</td></tr>`).join('');
  return `<h4 class="sub3">Gem slots</h4><div class="tabela-wrap"><table class="tab"><tr><th>Vessels</th><th class="r">Precisa</th><th class="r">Com os seus pontos</th></tr>${gem}</table></div>
    ${opc ? `<h4 class="sub3">Opcionais</h4><p class="dica" style="margin:0 0 4px">Na ordem da lista: o número inclui tudo o que está acima. "Sozinho" = o custo dele como único opcional.</p>
      <div class="tabela-wrap"><table class="tab"><tr><th>Opcional</th><th class="r">Precisa</th><th class="r">Com os seus pontos</th><th class="r">Sozinho</th></tr>${opc}</table></div>` : ''}
    ${rev ? `<h4 class="sub3">Próximos estágios de revelação</h4><div class="tabela-wrap"><table class="tab"><tr><th>Meta</th><th class="r">Precisa</th><th class="r">Com os seus pontos</th><th>Com gemas de revelação</th></tr>${rev}</table></div>` : ''}`;
}
async function otmCalcularPn() {
  if (OTM.pn || !OTM.res) return;
  OTM.pn = null;
  try { OTM.pn = await otmPedirWorker({ tipo: 'pontos', vocacao: OTM.res.vocacao, voc: OTM.dados.vocacoes[OTM.res.vocacao], pedido: OTM.res.pedido, resultado: OTM.res.status === 'ok' ? OTM.res : null }); }
  catch (e) { OTM.pn = { erro: 'O cálculo falhou: ' + e.message }; }
  if ($('otm-pn')) $('otm-pn').innerHTML = otmPnHtml();
}
const otmRodaAtual = () => (OTM.res ? (OTM.res.status === 'ok' ? OTM.res.variantes[OTM.variante] || OTM.res : OTM.res.noMinimo) : null);
$('otm-res').addEventListener('toggle', (e) => { if (e.target.id !== 'otm-pn-det') return; OTM.pnAberto = e.target.open; if (e.target.open) otmCalcularPn(); }, true);
$('otm-res').addEventListener('click', async (e) => {
  const v = e.target.closest('[data-otm-var]'), fatia = e.target.closest('[data-otm-fatia]'), roda = otmRodaAtual();
  if (v) { OTM.variante = +v.dataset.otmVar; OTM.fatia = null; otmDesenharResultado(); return; }
  if (fatia) { otmEscolherFatia(+fatia.dataset.otmFatia); return; }
  if (!roda) return;
  if (e.target.id === 'otm-planner') { wodAba('planner'); abrirRodaNoPlanner(roda.codigo); }
  else if (e.target.id === 'otm-copiar') { (await api.copiar(roda.codigo)) ? toast('Código da roda copiado.') : toast('Não consegui copiar.', true); }
  else if (e.target.id === 'otm-salvar') {
    const r = await api.roda_adicionar($('otm-nome').value, roda.codigo, MEUS.atual || '');
    if (!r.ok) { toast(r.erro, true); return; }
    toast(`Salva como "${r.roda.titulo}" (${r.roda.vocacao}).`);
    await carregarRodas();
  }
});
$('otm-res').addEventListener('keydown', (e) => {
  const fatia = e.target.closest('[data-otm-fatia]');
  if (fatia && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); otmEscolherFatia(+fatia.dataset.otmFatia); }
});
// só na roda de reserva (fatias coloridas): mostra o detalhe da fatia sem redesenhar o resto
function otmEscolherFatia(i) {
  const roda = otmRodaAtual(); if (!roda) return;
  OTM.fatia = i;
  document.querySelectorAll('#otm-res [data-otm-fatia]').forEach((g) => g.classList.toggle('sel', +g.dataset.otmFatia === i));
  if ($('otm-fatia-info')) $('otm-fatia-info').innerHTML = otmDetalheFatia(OTM.dados.vocacoes[OTM.res.vocacao], roda.vetor);
}

// ---------- abas do menu Wheel of Destiny ----------
function wodAba(aba) {
  document.querySelectorAll('[data-wod-aba]').forEach((x) => x.classList.toggle('on', x.dataset.wodAba === aba));
  $('wod-aba-planner').style.display = aba === 'planner' ? '' : 'none';
  $('wod-aba-otimizador').style.display = aba === 'otimizador' ? '' : 'none';
  try { localStorage.setItem('zt-wod-aba', aba); } catch (e) { /* só conveniência */ }
  if (aba === 'otimizador') abrirOtimizador(); else abrirWod();
}
$('wod-abas').addEventListener('click', (e) => { const a = e.target.closest('[data-wod-aba]'); if (a) wodAba(a.dataset.wodAba); });
$('wod-abas').addEventListener('keydown', (e) => { const a = e.target.closest('[data-wod-aba]'); if (a && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); wodAba(a.dataset.wodAba); } });
// ao entrar no menu: volta na última aba usada
function wodAbrirMenu() {
  let aba = 'planner';
  try { aba = localStorage.getItem('zt-wod-aba') === 'otimizador' ? 'otimizador' : 'planner'; } catch (e) { /* padrão */ }
  wodAba(aba);
}
