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

// ---------- formulário ----------
function otmOpcaoTexto(op) {
  if (op.tipo === 'revelacao') return `${otmDominio(op.dominio).revelacao} estágio ${OTM_ROMANO[op.estagio]}`;
  if (op.tipo === 'gemas') return `${op.n} gem vessels`;
  return `${otmPerk(op.perk).nome}${op.copias > 1 ? ' ×' + op.copias : ''}`;
}
function otmMetaTexto(m) {
  if (m === 'gemas') return 'Próximo gem vessel';
  if (m === 'skill') return 'Skill +1';
  if (m.startsWith('perk:')) return `${otmPerk(m.slice(5)).nome}: próxima fatia`;
  if (m.startsWith('revelacao:')) return `${otmDominio(m.slice(10)).revelacao}: próximo estágio`;
  return OTM_STATS[m] || m;
}
// perks agrupados por tipo para os <select>
function otmOpcoesPerks(semGemas = false) {
  const voc = otmVoc(), grupos = {};
  voc.perks.forEach((p) => {
    const f = voc.fatias.find((x) => x.perk === p.id);
    const tipo = f ? f.tipo : 'passive';
    if (semGemas && tipo === 'gemVessel') return;
    (grupos[tipo] ||= []).push(p);
  });
  return Object.entries(grupos).map(([t, ps]) => `<optgroup label="${esc(OTM_TIPOS[t] || t)}">${ps.map((p) => `<option value="${esc(p.id)}">${esc(p.nome)}${p.max > 1 ? ` (até ${p.max})` : ''}</option>`).join('')}</optgroup>`).join('');
}
const otmLinhaLista = (texto, chave, k, total, extra = '') => `<div class="otm-item"><span>${k + 1}. ${esc(texto)}</span>${extra}
  <span class="otm-acoes"><button class="btn btn-sm" data-otm-subir="${chave}:${k}" ${k ? '' : 'disabled'} title="Subir (mais prioridade)">↑</button><button class="btn btn-sm" data-otm-descer="${chave}:${k}" ${k < total - 1 ? '' : 'disabled'} title="Descer">↓</button><button class="btn btn-sm btn-danger" data-otm-tirar="${chave}:${k}" title="Tirar">✕</button></span></div>`;

function otmDesenharForm() {
  const voc = otmVoc(), p = otmPed(), ob = p.obrigatorio;
  const obPerks = ob.perks.map((x, k) => `<div class="otm-item"><span>${esc(otmPerk(x.perk).nome)}</span>
    ${otmPerk(x.perk).max > 1 ? `<label class="dica">cópias <input type="number" class="otm-num" min="1" max="${otmPerk(x.perk).max}" value="${x.copias}" data-otm-copias="${k}"></label>` : ''}
    <button class="btn btn-sm btn-danger" data-otm-tirar="obperk:${k}" title="Tirar">✕</button></div>`).join('') || '<div class="dica">Nenhum.</div>';
  const revs = voc.dominios.map((d) => `<label class="otm-rev"><span>${esc(d.revelacao)}</span><select data-otm-rev="${esc(d.id)}">${[0, 1, 2, 3].map((e) => `<option value="${e}" ${(ob.revelacao[d.id] || 0) === e ? 'selected' : ''}>${e ? 'pelo menos ' + OTM_ROMANO[e] + ' (' + voc.estagios[e - 1] + ')' : '—'}</option>`).join('')}</select></label>`).join('');
  const gemasRev = ob.gemasRevelacao.map((g, k) => `<span class="chip chip-neutro">${esc(otmDominio(g.dominio).revelacao)} +${voc.bonus_gema[g.grau - 1]} <button class="otm-x" data-otm-tirar="gemrev:${k}" title="Tirar a gema">✕</button></span>`).join(' ');
  const opcionais = p.opcionais.map((op, k) => otmLinhaLista(otmOpcaoTexto(op), 'opc', k, p.opcionais.length)).join('') || '<div class="dica">Nenhum. Adicione abaixo.</div>';
  const sobras = p.sobras.map((m, k) => otmLinhaLista(otmMetaTexto(m), 'sob', k, p.sobras.length)).join('') || '<div class="dica">Nenhuma: os pontos extras vão para onde der.</div>';
  const metas = ['gemas', 'skill', ...voc.dominios.map((d) => 'revelacao:' + d.id), ...Object.keys(OTM_STATS), ...voc.perks.filter((x) => !x.id.startsWith('revelation-mastery') && x.id !== 'gem-vessel').map((x) => 'perk:' + x.id)]
    .filter((m) => !p.sobras.includes(m));
  $('otm-form').innerHTML = `
    <div class="otm-linha">
      <label><span class="campo-label">Vocação</span><select id="otm-voc">${OTM_VOCS.map(([v, n]) => `<option value="${v}" ${v === OTM.voc ? 'selected' : ''}>${n}</option>`).join('')}</select></label>
      <label><span class="campo-label">Pontos</span><input type="number" id="otm-pontos" class="otm-num" min="0" max="4000" value="${p.pontos}" title="Pontos de promoção: level − 50 + pergaminhos"></label>
      <label><span class="campo-label">Mín. de gem vessels</span><select id="otm-gemas">${[0, 1, 2, 3, 4, 5, 6, 7, 8].map((n) => `<option value="${n}" ${ob.gemas === n ? 'selected' : ''}>${n}</option>`).join('')}</select></label>
    </div>
    <h4 class="sub3">Obrigatórios</h4>
    <div class="otm-lista">${obPerks}</div>
    <div class="otm-linha"><select id="otm-add-ob"><option value="">+ perk obrigatório…</option>${otmOpcoesPerks(true)}</select></div>
    <h4 class="sub3">Revelação: estágio mínimo</h4>
    <div class="otm-revs">${revs}</div>
    <div class="otm-linha"><select id="otm-gemrev-dom">${voc.dominios.map((d) => `<option value="${esc(d.id)}">${esc(d.revelacao)}</option>`).join('')}</select>
      <select id="otm-gemrev-grau">${voc.bonus_gema.map((b, k) => `<option value="${k + 1}" ${k === 3 ? 'selected' : ''}>grau ${k + 1}: +${b}</option>`).join('')}</select>
      <button class="btn btn-sm" id="otm-gemrev-add" title="Uma gema greater com mod de Revelação que você tem">+ gema de revelação</button></div>
    <div class="otm-linha">${gemasRev}</div>
    <p class="dica" style="margin:4px 0 0">Estágios I / II / III = ${voc.estagios.join(' / ')} pontos no quadrante. A Revelation Mastery cheia soma +${voc.bonus_mastery}. A gema de revelação só vale num slot greater liberado (3º, 5º, 7º e 8º vessel) e o cálculo só usa se precisar.</p>
    <h4 class="sub3">Opcionais (a ordem é a prioridade)</h4>
    <p class="dica" style="margin:0 0 6px">Um opcional de cima vale mais que todos os de baixo juntos.</p>
    <div class="otm-lista">${opcionais}</div>
    <div class="otm-linha"><select id="otm-add-opc"><option value="">+ opcional…</option>
      <optgroup label="Perks">${voc.perks.filter((x) => x.id !== 'gem-vessel').map((x) => `<option value="perk:${esc(x.id)}">${esc(x.nome)}</option>`).join('')}</optgroup>
      <optgroup label="Revelação">${voc.dominios.flatMap((d) => [1, 2, 3].map((e) => `<option value="rev:${esc(d.id)}:${e}">${esc(d.revelacao)} estágio ${OTM_ROMANO[e]}</option>`)).join('')}</optgroup>
      <optgroup label="Gem vessels">${[1, 2, 3, 4, 5, 6, 7, 8].map((n) => `<option value="gemas:${n}">${n} vessels (${esc(voc.ordem_gemas[n - 1])})</option>`).join('')}</optgroup></select></div>
    <h4 class="sub3">Pontos extras (a ordem é a prioridade)</h4>
    <div class="otm-lista">${sobras}</div>
    <div class="otm-linha"><select id="otm-add-sob"><option value="">+ meta…</option>${metas.map((m) => `<option value="${esc(m)}">${esc(otmMetaTexto(m))}</option>`).join('')}</select></div>
    <div class="otm-linha" style="margin-top:12px"><button class="btn btn-primary" id="otm-calcular">Calcular</button><span class="dica" id="otm-status"></span></div>`;
}

function otmMudou() { otmGuardar(); otmDesenharForm(); }
$('otm-form').addEventListener('change', (e) => {
  const t = e.target, p = otmPed(), ob = p.obrigatorio;
  if (t.id === 'otm-voc') { OTM.voc = t.value; OTM.res = null; otmMudou(); otmCalcular(); return; }
  if (t.id === 'otm-pontos') p.pontos = Math.max(0, Math.min(4000, Math.floor(+t.value || 0)));
  else if (t.id === 'otm-gemas') ob.gemas = +t.value;
  else if (t.dataset.otmRev) { const e2 = +t.value; if (e2) ob.revelacao[t.dataset.otmRev] = e2; else delete ob.revelacao[t.dataset.otmRev]; }
  else if (t.dataset.otmCopias !== undefined) { const x = ob.perks[+t.dataset.otmCopias]; x.copias = Math.max(1, Math.min(otmPerk(x.perk).max, Math.floor(+t.value || 1))); }
  else if (t.id === 'otm-add-ob' && t.value) { if (!ob.perks.some((x) => x.perk === t.value)) ob.perks.push({ perk: t.value, copias: 1 }); }
  else if (t.id === 'otm-add-opc' && t.value) {
    const [tipo, a, b] = t.value.split(':');
    p.opcionais.push(tipo === 'perk' ? { tipo: 'perk', perk: a, copias: otmPerk(a).max > 1 ? otmPerk(a).max : 1 } : tipo === 'rev' ? { tipo: 'revelacao', dominio: a, estagio: +b } : { tipo: 'gemas', n: +a });
  } else if (t.id === 'otm-add-sob' && t.value) p.sobras.push(t.value);
  else return;
  otmMudou();
});
$('otm-form').addEventListener('click', (e) => {
  const b = e.target.closest('button'); if (!b) return;
  const p = otmPed(), ob = p.obrigatorio;
  if (b.id === 'otm-calcular') { otmCalcular(); return; }
  if (b.id === 'otm-gemrev-add') { if (ob.gemasRevelacao.length < 4) ob.gemasRevelacao.push({ dominio: $('otm-gemrev-dom').value, grau: +$('otm-gemrev-grau').value }); else toast('No máximo 4 gemas (são 4 slots greater).', true); otmMudou(); return; }
  const [acao, alvo] = ['otmSubir', 'otmDescer', 'otmTirar'].map((k) => [k, b.dataset[k]]).find(([, v]) => v !== undefined) || [];
  if (!acao) return;
  const [lista, k0] = alvo.split(':'), k = +k0;
  const arr = lista === 'opc' ? p.opcionais : lista === 'sob' ? p.sobras : lista === 'obperk' ? ob.perks : ob.gemasRevelacao;
  if (acao === 'otmTirar') arr.splice(k, 1);
  else { const j = acao === 'otmSubir' ? k - 1 : k + 1; if (j >= 0 && j < arr.length) [arr[k], arr[j]] = [arr[j], arr[k]]; }
  otmMudou();
});

// ---------- cálculo ----------
async function otmCalcular() {
  const st = $('otm-status'), btn = $('otm-calcular');
  if (st) st.textContent = 'Calculando…';
  if (btn) btn.disabled = true;
  OTM.pn = null;
  try {
    OTM.res = await otmPedirWorker({ tipo: 'otimizar', vocacao: OTM.voc, voc: otmVoc(), pedido: otmPed() });
    OTM.res.vocacao = OTM.voc;
    OTM.variante = 0; OTM.fatia = null;
    if (st) st.textContent = '';
  } catch (e) {
    OTM.res = null;
    if (st) st.textContent = 'O cálculo falhou: ' + e.message;
  }
  if (btn) btn.disabled = false;
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
  const voc = OTM.dados.vocacoes[r.vocacao], ped = OTM.pedidos[r.vocacao];
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
  try { OTM.pn = await otmPedirWorker({ tipo: 'pontos', vocacao: OTM.res.vocacao, voc: OTM.dados.vocacoes[OTM.res.vocacao], pedido: OTM.pedidos[OTM.res.vocacao], resultado: OTM.res.status === 'ok' ? OTM.res : null }); }
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
