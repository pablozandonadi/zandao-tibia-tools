// Character Sets: o set é uma "foto" no layout do inventário do Tibia (espaços vazios até você escolher o item).
// Cadastro em Configurações, escolha na hunt e janela "Ver set".
// Depende de index.html: $, esc, toast, api, H, escolher, redesenharPerso. Carregado depois do roda.js.

// posição de cada espaço na foto: [coluna, linha]
const SET_POS = { amuleto: [1, 1], cabeca: [2, 1], arma: [1, 2], armadura: [2, 2], mao: [3, 2], anel: [1, 3], pernas: [2, 3], trinket: [3, 3], botas: [2, 4] };
const SET_GRUPOS = [['Ataque', ['arma', 'anel', 'amuleto']], ['Defesa', ['cabeca', 'armadura', 'pernas', 'botas', 'mao', 'trinket']]];
const SET_MAX_CONS = 12;
// silhueta de cada espaço vazio (como no inventário do Tibia): o sprite de um item típico do espaço, escurecido pelo CSS
const SET_SIL = {
  amuleto: 'https://static.wikia.nocookie.net/tibia/images/4/42/Platinum_Amulet.gif/revision/latest?cb=20050531085148&path-prefix=en',
  cabeca: 'https://static.wikia.nocookie.net/tibia/images/c/cd/Steel_Helmet.gif/revision/latest?cb=20050531085331&path-prefix=en',
  arma: 'https://static.wikia.nocookie.net/tibia/images/1/1f/Sword.gif/revision/latest?cb=20120411043434&path-prefix=en',
  armadura: 'https://static.wikia.nocookie.net/tibia/images/2/2e/Plate_Armor.gif/revision/latest?cb=20171214210907&path-prefix=en',
  mao: 'https://static.wikia.nocookie.net/tibia/images/1/17/Steel_Shield.gif/revision/latest?cb=20050614194907&path-prefix=en',
  anel: 'https://static.wikia.nocookie.net/tibia/images/3/3b/Gold_Ring.gif/revision/latest?cb=20060423182854&path-prefix=en',
  pernas: 'https://static.wikia.nocookie.net/tibia/images/6/6f/Plate_Legs.gif/revision/latest?cb=20050524135924&path-prefix=en',
  botas: 'https://static.wikia.nocookie.net/tibia/images/9/94/Leather_Boots.gif/revision/latest?cb=20050523051338&path-prefix=en',
  trinket: 'https://static.wikia.nocookie.net/tibia/images/0/02/Cursed_Coin.gif/revision/latest?cb=20260805120441&path-prefix=en',
};
let SETS = [];                 // sets cadastrados: [{id, titulo, itens, consumiveis}]
let SET_TAB = null;            // {slots: [[chave, rótulo]], embuimentos: [{nome, sub}]}
const SET_ITENS = {};          // itens da TibiaWiki por slot (baixados na 1ª vez que o slot é aberto)
const rotuloSlot = (k) => ((SET_TAB && SET_TAB.slots.find((s) => s[0] === k)) || [k, k])[1];

// vocação (sorcerer, knight...) a partir do texto do tibia.com ("Master Sorcerer", "Elite Knight"...)
const VOC_DE = (txt) => ['sorcerer', 'druid', 'knight', 'paladin', 'monk'].find((v) => (txt || '').toLowerCase().includes(v)) || '';
const vocEmUso = () => { const p = acharMeu(MEUS.atual); return p ? VOC_DE(p.vocacao) : ''; };   // do personagem "em uso" (Configurações)
const nomeVoc = (v) => (v ? v[0].toUpperCase() + v.slice(1) : '');

async function carregarSets() {
  SETS = (await api.set_listar()) || [];
  if (!SET_TAB) SET_TAB = await api.set_tabelas();
  return SETS;
}
// set da última hunt desse personagem (valor inicial de uma hunt nova); {} = sem set
const setInicial = async (personagem) => (await api.hunt_ultimo_set(personagem || '')) || {};

// ---------- a foto do set ----------
const imgCel = (it) => (it.imagem ? `<img src="${esc(it.imagem)}" alt="" onerror="this.style.visibility='hidden'">` : `<span class="set-cel-ini">${esc(it.nome.slice(0, 2))}</span>`);
// s: {itens, consumiveis}; editavel: as células viram botões; sel: espaço em destaque; mini: tamanho pequeno
function htmlFotoSet(s, { editavel = false, sel = '', mini = false } = {}) {
  const itens = (s && s.itens) || {}, cons = (s && s.consumiveis) || [];
  const tag = editavel ? 'button' : 'div';
  const cel = (k) => {
    const it = itens[k], [c, l] = SET_POS[k];
    const dica = it ? [`${rotuloSlot(k)}: ${it.nome}`, it.desc, (it.imbues || []).join(', ')].filter(Boolean).join(' — ') : rotuloSlot(k);
    return `<${tag} class="set-cel ${it ? 'cheia' : 'vazia'} ${sel === k ? 'sel' : ''}" style="grid-column:${c};grid-row:${l}" title="${esc(dica)}"
      ${editavel ? `data-set-cel="${k}"` : ''}>${it ? imgCel(it) : `<img class="set-sil" src="${SET_SIL[k]}" alt="" onerror="this.style.display='none'">`}</${tag}>`;
  };
  const consHtml = cons.map((c, i) => `<${tag} class="set-cel cheia" title="${esc(c.nome)}${editavel ? ' (clique para tirar)' : ''}" ${editavel ? `data-set-cons-tirar="${i}"` : ''}>${imgCel(c)}</${tag}>`).join('')
    + (editavel && cons.length < SET_MAX_CONS ? '<button class="set-cel mais" data-set-cons-add title="Adicionar consumível">+</button>' : '');
  return `<div class="set-foto ${mini ? 'mini' : ''}"><div class="set-grade-eq">${Object.keys(SET_POS).map(cel).join('')}</div>
    ${consHtml ? `<div class="set-cons-rotulo">Consumíveis</div><div class="set-cons">${consHtml}</div>` : ''}</div>`;
}

// ---------- Combat Stats: a soma dos itens e dos embuimentos (calculada em stats_set.py) ----------
function htmlStatsSet(linhas, titulo = '📊 Combat Stats', nota = 'Soma dos itens, dos embuimentos Powerful e dos perks da arma (valores da TibiaWiki).') {
  if (!linhas || !linhas.length) return '<p class="dica" style="margin:0">Escolha itens para ver a soma dos stats.</p>';
  const grupo = (nome) => {
    const l = linhas.filter((x) => x.grupo === nome);
    return l.length ? `<div class="stats-grupo"><h5>${nome}</h5>${l.map((x) => `<div class="stat-lin" ${x.detalhe ? `title="${esc(x.detalhe)}"` : ''}><span>${esc(x.rotulo)}</span><b>${esc(x.texto)}</b></div>${x.detalhe ? `<small class="stat-det">${esc(x.detalhe)}</small>` : ''}`).join('')}</div>` : '';
  };
  return `<div class="stats-set"><h4>${titulo}</h4><div class="stats-grade">${['Defesa', 'Ataque', 'Skills', 'Perks da arma', 'Prey', 'Charms', 'Roda', 'Outros'].map(grupo).join('')}</div>
    <p class="dica" style="margin:6px 0 0">${nota}</p></div>`;
}

// ---------- Combat Stats da hunt (set + prey + charms + roda) ----------
const RODA_PEND = {};
// o resumo da roda vem do planner oficial: se ainda não foi guardado, abre o planner escondido uma vez para calcular
function garantirResumoRoda(codigo) {
  if (RODA_PEND[codigo]) return RODA_PEND[codigo];
  RODA_PEND[codigo] = (async () => {
    if (RODA_RESUMO[codigo] || await api.roda_resumo(codigo)) return;
    let caixa = $('roda-oculta');
    if (!caixa) {
      caixa = document.createElement('div');
      caixa.id = 'roda-oculta';
      caixa.style.cssText = 'position:fixed;left:-3000px;top:0;width:1100px;height:800px;overflow:hidden;opacity:0;pointer-events:none';
      document.body.appendChild(caixa);
    }
    const alvo = document.createElement('div');
    caixa.appendChild(alvo);
    await new Promise((fim) => {
      const limite = setTimeout(fim, 25000);
      mostrarRoda(alvo, codigo, { aoResumo: (c, s) => { guardarResumoRoda(c, s); clearTimeout(limite); fim(); } }).then((ok) => { if (!ok) fim(); });
    });
    alvo.remove();
  })();
  return RODA_PEND[codigo];
}
async function atualizarCombatHunt() {
  if (!$('h-combat')) return;
  const e = H.entrada, codigo = e.roda && e.roda.codigo;
  let linhas = await api.hunt_stats(e.set || null, e.prey || [], e.charms || [], e.roda || null);
  if ($('h-combat')) $('h-combat').innerHTML = linhas.length ? htmlStatsSet(linhas, '📊 Combat Stats desta hunt', 'Set + prey + charms + roda. Prey e charms valem só contra a criatura escolhida (passe o mouse para ver).') : '';
  if (codigo && !RODA_RESUMO[codigo] && !(await api.roda_resumo(codigo))) {   // roda sem resumo guardado: calcula e atualiza o painel
    await garantirResumoRoda(codigo);
    linhas = await api.hunt_stats(e.set || null, e.prey || [], e.charms || [], e.roda || null);
    if ($('h-combat')) $('h-combat').innerHTML = linhas.length ? htmlStatsSet(linhas, '📊 Combat Stats desta hunt', 'Set + prey + charms + roda. Prey e charms valem só contra a criatura escolhida (passe o mouse para ver).') : '';
  }
}
async function preencherStats(alvoId, set) {
  const linhas = await api.set_stats(set);
  const el = $(alvoId);
  if (el) el.innerHTML = htmlStatsSet(linhas);
}

// ---------- a vista de um set (janela "Ver set": a foto e, embaixo, o detalhe por grupo) ----------
function htmlItemSet(slot, it) {
  const imb = (it.imbues || []).map((e) => `<span class="chip chip-neutro" style="font-size:.64rem">${esc(e)}</span>`).join(' ');
  const prof = it.prof ? ` <span class="chip chip-neutro" style="font-size:.64rem">Proficiência ${it.prof.nivel}${it.prof.maestria ? ' · Maestria' : ''}${(it.prof.trocas || []).filter((t) => t && t.opcao).length ? ' · ' + it.prof.trocas.filter((t) => t && t.opcao).length + ' troca(s)' : ''}</span>` : '';
  return `<div class="set-item"><span class="set-img">${it.imagem ? `<img src="${esc(it.imagem)}" alt="" onerror="this.style.visibility='hidden'">` : ''}</span><div class="set-item-txt"><small class="dim">${esc(rotuloSlot(slot))}</small><b>${esc(it.nome)}</b>
    ${it.desc ? `<span class="dica">${esc(it.desc)}</span>` : ''}${imb || prof ? `<div>${imb}${prof}</div>` : ''}</div></div>`;
}
function htmlSetVista(s) {
  if (!s || !s.itens) return '<p class="dica">Sem set nesta hunt.</p>';
  const grupo = ([nome, slots]) => {
    const itens = slots.filter((k) => s.itens[k]);
    return `<div class="set-grupo"><h4>${nome}</h4>${itens.length ? itens.map((k) => htmlItemSet(k, s.itens[k])).join('') : '<p class="dica">Nada escolhido.</p>'}</div>`;
  };
  const cons = (s.consumiveis || []).length ? `<div class="set-grupo"><h4>Consumíveis</h4><div>${s.consumiveis.map((c) => `<span class="chip chip-neutro">${esc(c.nome)}</span>`).join(' ')}</div></div>` : '';
  return `${htmlFotoSet(s)}<div id="set-vista-stats"></div><div class="set-vista">${SET_GRUPOS.map(grupo).join('')}${cons}</div>`;
}
function abrirVistaSet(s) {
  $('set-vista-titulo').textContent = s && s.titulo ? s.titulo : 'Set';
  $('set-vista-corpo').innerHTML = htmlSetVista(s);
  $('modal-set').style.display = 'flex';
  if (s && s.itens) preencherStats('set-vista-stats', s);
}
$('set-vista-fechar').addEventListener('click', () => { $('modal-set').style.display = 'none'; });
$('modal-set').addEventListener('click', (e) => { if (e.target === $('modal-set')) $('modal-set').style.display = 'none'; });

// ---------- Configurações: lista e editor ----------
let SETED = null;   // set em edição: {id|null, titulo, itens, consumiveis, voc, sel}
const qtdItens = (s) => Object.keys(s.itens || {}).length;
function desenharSetsConfig() {
  $('sets-lista').innerHTML = SETS.length ? SETS.map((s) => `<div class="roda-item">
      <div class="roda-nome"><b>${esc(s.titulo)}</b> ${s.voc ? `<span class="chip chip-neutro">${nomeVoc(s.voc)}</span>` : ''} <span class="chip chip-neutro">${qtdItens(s)} ite${qtdItens(s) === 1 ? 'm' : 'ns'}</span></div>
      <div class="acoes"><button class="btn btn-sm" data-set-ver="${esc(s.id)}">👁 Ver</button><button class="btn btn-sm" data-set-editar="${esc(s.id)}">🛠 Editar</button>
        <button class="btn btn-sm btn-danger" data-set-apagar="${esc(s.id)}" title="Apagar">✕</button></div></div>`).join('')
    : '<div class="dica">Nenhum set cadastrado ainda.</div>';
}
async function montarSetsConfig() { await carregarSets(); desenharSetsConfig(); }

// ---------- proficiência da arma e Perk Shaping (dados da TibiaWiki em português; ver proficiencia.py) ----------
const SET_SHAPING = {};   // opções do Perk Shaping por vocação ('' = todas), baixadas uma vez
function numTexto(t) {
  const m = /^([+-]?[0-9]+(?:[.,][0-9]+)?)(%?)[ ]*(.*)$/.exec((t || '').trim());
  return m ? { v: parseFloat(m[1].replace(',', '.')), u: m[2], l: m[3] } : null;
}
// texto da opção no rank (reta entre o rank 0 e o rank 10 da wiki), igual ao proficiencia.texto_no_rank
function textoRank(op, rank) {
  const a = numTexto(op.rank0), b = numTexto(op.rank10);
  if (!a || !b) return rank ? op.rank10 : op.rank0;
  const v = a.v + (b.v - a.v) * rank / 10;
  return `${v < 0 ? '-' : '+'}${(+Math.abs(v).toFixed(2)).toString()}${a.u} ${a.l}`.trim();
}
async function carregarPerksArma(anterior) {
  const it = SETED.itens.arma;
  if (!it) return;
  if (anterior && anterior.nome === it.nome && anterior.perks) { it.perks = anterior.perks; it.prof = anterior.prof; return; }   // mesma arma: mantém as escolhas
  toast('Buscando a proficiência da arma na TibiaWiki (só na primeira vez, ~10 s)...');
  const r = await api.set_perks(it.nome);
  SET_ICONES = r.icones || SET_ICONES;
  if (r.colunas && r.colunas.length) { it.perks = r.colunas; it.prof = { nivel: 7, maestria: false, escolhas: [], trocas: [] }; }
  else { delete it.perks; delete it.prof; }
  const voc = SETED.voc || '';
  if (!SET_SHAPING[voc]) SET_SHAPING[voc] = (await api.set_shaping(voc)) || [];
}

// ícone de um perk como na wiki: moldura, ícone do tipo e o selo pequeno (aug) no canto
let SET_ICONES = {};
function icoPerk(tipo, aug) {
  const u = (n) => SET_ICONES[n] || '';
  const img = (cls, n) => (u(n) ? `<img class="${cls}" src="${esc(u(n))}" alt="" onerror="this.style.display='none'">` : '');
  return `<span class="prof-ico">${img('b', 'Proficiency_Border')}${img('i', 'Proficiency_' + tipo)}${aug ? img('a', 'Proficiency_Augment_' + aug) : ''}</span>`;
}
// valor curto para o canto do ícone: "+5.00% critical..." -> "5%"; "+1 Magic Level" -> "1"
const valorCurto = (texto) => { const n = numTexto(texto); return n ? `${+Math.abs(n.v).toFixed(2)}${n.u}` : ''; };
// reshape ativo na coluna c (índice em prof.trocas) ou -1. O 1º precisa de 1 nível; o 2º, de Maestria.
function reshapeDa(p, c) {
  return (p.trocas || []).findIndex((t, i) => t && t.coluna === c && t.opcao && p.nivel >= 1 && (i === 0 || p.maestria));
}
function htmlProfArma(it) {
  const p = it.prof, opcoes = SET_SHAPING[SETED.voc || ''] || [], nivel = p.nivel;
  const usados = (p.trocas || []).filter((t) => t && t.opcao).length, max = nivel >= 1 ? (p.maestria ? 2 : 1) : 0;
  const colunas = it.perks.map((col, ci) => {
    const c = ci + 1, livre = c <= nivel, ri = reshapeDa(p, c);
    const sel = Number.isInteger(p.escolhas[ci]) && p.escolhas[ci] < col.length ? p.escolhas[ci] : 0;
    const t = ri >= 0 ? p.trocas[ri] : null, op = t && opcoes.find((o) => o.nome === t.opcao);
    const tiles = col.map((o, oi) => {
      if (oi === sel && op) {   // o perk escolhido foi trocado pelo reshape: mostra a opção nova no mesmo lugar
        const tx = textoRank(op, t.rank || 0);
        return `<button class="prof-tile sel reshaped" data-prof-pick="${ci}:${oi}" title="Reshape (rank ${t.rank || 0}): ${esc(tx)} | Original: ${esc(o.texto)}">${icoPerk(op.perk, op.modifier)}<b class="prof-val">${esc(valorCurto(tx))}</b></button>`;
      }
      return `<button class="prof-tile ${oi === sel ? 'sel' : 'off'}" data-prof-pick="${ci}:${oi}" ${livre ? '' : 'disabled'} title="${esc(o.texto)}">${icoPerk(o.tipo, o.aug)}<b class="prof-val">${esc(valorCurto(o.texto))}</b></button>`;
    }).join('');
    const pode = livre && (ri >= 0 || usados < max);
    const dica = pode ? 'Trocar este perk por outra opção (Reshape)' : (max === 0 ? 'Precisa de 1 nível de proficiência' : 'Os reshapes já foram usados (o 2º precisa de Maestria)');
    const btn = livre ? `<button class="prof-shape ${ri >= 0 ? 'on' : ''}" data-reshape="${c}" ${pode ? '' : 'disabled'} title="${dica}">⚒ ${ri >= 0 ? 'rank ' + (t.rank || 0) : 'reshape'}</button>` : '';
    return `<div class="prof-colx ${livre ? '' : 'trav'}"><div class="prof-star">★ ${c}</div>${tiles}${btn}</div>`;
  }).join('');
  const lista = it.perks.map((col, ci) => {
    if (ci + 1 > nivel) return '';
    const sel = Number.isInteger(p.escolhas[ci]) && p.escolhas[ci] < col.length ? p.escolhas[ci] : 0, ri = reshapeDa(p, ci + 1);
    const t = ri >= 0 ? p.trocas[ri] : null, op = t && opcoes.find((o) => o.nome === t.opcao);
    const tx = op ? textoRank(op, t.rank || 0) : (col[sel] || {}).texto;
    return tx ? `<li><b>★ ${ci + 1}</b> ${esc(tx)}${op ? ` <span class="chip chip-neutro" style="font-size:.6rem">reshape · rank ${t.rank || 0}</span>` : ''}</li>` : '';
  }).join('');
  return `<div class="prof-box"><h5>Proficiência da arma · ${esc(it.nome)}</h5>
    <div class="roda-linha"><label>Nível de proficiência <select data-prof-nivel>${Array.from({ length: 8 }, (_, n) => `<option value="${n}" ${n === nivel ? 'selected' : ''}>${n}</option>`).join('')}</select></label>
      <label><input type="checkbox" data-prof-maestria ${p.maestria ? 'checked' : ''}> Maestria</label>
      <span class="dica">Reshapes: ${usados}/${max}${max < 2 ? (max === 0 ? ' (precisa de 1 nível)' : ' (o 2º precisa de Maestria)') : ''}</span></div>
    <div class="prof-grade">${colunas}</div>
    <ul class="prof-lista">${lista}</ul>
    <p class="dica" style="margin:4px 0 0">Clique no perk que você usa em cada nível. "⚒ reshape" troca o perk escolhido por outra opção, no mesmo lugar.</p></div>`;
}

// ---------- janela do Reshape: escolhe a opção que substitui o perk da coluna ----------
let RS = null;   // {coluna, rank}
function abrirReshape(coluna) {
  const p = SETED.itens.arma.prof, ri = reshapeDa(p, coluna);
  RS = { coluna, rank: ri >= 0 ? (p.trocas[ri].rank || 0) : 10 };
  $('rs-titulo').textContent = `Reshape · nível ${coluna}`;
  $('rs-filtro').value = '';
  $('rs-rank').value = String(RS.rank);
  $('rs-limpar').style.display = ri >= 0 ? '' : 'none';
  desenharReshape();
  $('modal-reshape').style.display = 'flex';
  $('rs-filtro').focus();
}
function desenharReshape() {
  const voc = SETED.voc || '', opcoes = SET_SHAPING[voc] || [], f = $('rs-filtro').value.trim().toLowerCase();
  const p = SETED.itens.arma.prof, ri = reshapeDa(p, RS.coluna), atual = ri >= 0 ? p.trocas[ri].opcao : '';
  const item = (o) => { const tx = textoRank(o, RS.rank);
    return `<button class="rs-card ${o.nome === atual ? 'on' : ''}" data-rs="${esc(o.nome)}" title="${esc(o.nome)}: ${esc(tx)}">${icoPerk(o.perk, o.modifier)}<b class="rs-val">${esc(valorCurto(tx))}</b><span class="rs-nome">${esc(o.nome.replace(/^Spell Augment /, ''))}</span></button>`; };
  const grupo = (titulo, lista) => { const l = lista.filter((o) => !f || (o.nome + ' ' + o.rank0).toLowerCase().includes(f)); return l.length ? `<h5>${titulo} <span class="dica">(${l.length})</span></h5><div class="rs-grade">${l.map(item).join('')}</div>` : ''; };
  $('rs-lista').innerHTML = grupo('Todas as vocações', opcoes.filter((o) => !o.voc)) + (voc ? grupo(nomeVoc(voc), opcoes.filter((o) => o.voc === voc)) : '') || '<p class="dica">Nenhuma opção com esse nome.</p>';
}
function aplicarReshape(nome) {
  const p = SETED.itens.arma.prof;
  let ri = reshapeDa(p, RS.coluna);
  p.trocas = [p.trocas[0] || {}, p.trocas[1] || {}];
  if (nome === null) { if (ri >= 0) p.trocas[ri] = {}; }
  else {
    if (ri < 0) ri = !p.trocas[0].opcao ? 0 : (p.maestria && !p.trocas[1].opcao ? 1 : -1);
    if (ri < 0) { toast('Os reshapes já foram usados (o 2º precisa de Maestria).', true); return; }
    p.trocas[ri] = { coluna: RS.coluna, opcao: nome, rank: RS.rank };
  }
  p.trocas = p.trocas.filter((t) => t && t.opcao);   // sempre compacto: o que sobra vira a Troca 1 (a 2ª só existe com Maestria)
  $('modal-reshape').style.display = 'none';
  RS = null;
  desenharEditorSet();
}
$('rs-filtro').addEventListener('input', () => RS && desenharReshape());
$('rs-rank').addEventListener('change', () => {
  if (!RS) return;
  RS.rank = +$('rs-rank').value;
  const p = SETED.itens.arma.prof, ri = reshapeDa(p, RS.coluna);
  if (ri >= 0) { p.trocas[ri].rank = RS.rank; desenharEditorSet(); }   // já tem reshape: o rank vale na hora
  desenharReshape();
});
$('rs-lista').addEventListener('click', (e) => { const b = e.target.closest('[data-rs]'); if (b && RS) aplicarReshape(b.dataset.rs); });
$('rs-limpar').addEventListener('click', () => RS && aplicarReshape(null));
$('rs-fechar').addEventListener('click', () => { $('modal-reshape').style.display = 'none'; RS = null; });
$('modal-reshape').addEventListener('click', (e) => { if (e.target === $('modal-reshape')) { $('modal-reshape').style.display = 'none'; RS = null; } });

// o painel ao lado da foto: detalhe do espaço escolhido (embuimentos, trocar, tirar)
function htmlPainelSet() {
  const k = SETED.sel, it = k && SETED.itens[k];
  if (!it) return '<p class="dica" style="margin:0">Clique num espaço da foto para escolher o item. Espaço vazio = nada usado ali. Clique num item escolhido para ver os embuimentos, trocar ou tirar.</p>';
  const emb = SET_TAB.embuimentos;
  const sel = Array.from({ length: it.imbue || 0 }, (_, i) => `<select data-set-imb="${k}:${i}"><option value="">— embuimento ${i + 1} —</option>
    ${emb.map((e) => `<option value="${esc(e.nome)}" ${(it.imbues || [])[i] === e.nome ? 'selected' : ''}>${esc(e.nome)}${e.sub ? ' (' + esc(e.sub) + ')' : ''}</option>`).join('')}</select>`).join('');
  return `<small class="dim">${esc(rotuloSlot(k))}</small>
    <div class="set-item" style="margin:4px 0 8px"><span class="set-img">${it.imagem ? `<img src="${esc(it.imagem)}" alt="">` : ''}</span><div class="set-item-txt"><b>${esc(it.nome)}</b>${it.desc ? `<span class="dica">${esc(it.desc)}</span>` : ''}</div></div>
    ${sel || '<span class="dica">Este item não tem vaga de embuimento.</span>'}
    <div class="acoes" style="margin-top:8px"><button class="btn btn-sm" data-set-trocar="${k}">⇄ Trocar item</button><button class="btn btn-sm btn-danger" data-set-tirar="${k}">✕ Tirar</button></div>
    ${k === 'arma' && !(it.perks && it.prof) ? '<div class="acoes" style="margin-top:8px"><button class="btn btn-sm" data-set-perks>⚙ Carregar a proficiência da arma</button></div>' : ''}`;
}
function desenharEditorSet() {
  const s = SETED;
  $('sets-editor').innerHTML = `<div class="roda-barra"><input type="text" id="set-titulo" placeholder="Nome do set (ex.: Tokyo - Elite Knight)" maxlength="60" value="${esc(s.titulo)}">
      <select id="set-voc" title="Mostra só os itens dessa vocação ao escolher"><option value="">Todas as vocações</option>
      ${['knight', 'paladin', 'sorcerer', 'druid', 'monk'].map((v) => `<option value="${v}" ${s.voc === v ? 'selected' : ''}>${nomeVoc(v)}</option>`).join('')}</select>
      <span class="dica">${vocEmUso() ? `Personagem em uso: ${esc(MEUS.atual)} (${esc(nomeVoc(vocEmUso()))}). ` : ''}Só aparecem os itens da vocação escolhida.</span></div>
    <div class="set-editor-corpo"><div>${htmlFotoSet(s, { editavel: true, sel: s.sel })}</div><div class="set-painel">${htmlPainelSet()}<div id="set-stats"></div></div></div>
    ${s.itens.arma && s.itens.arma.perks && s.itens.arma.prof ? htmlProfArma(s.itens.arma) : ''}
    <div class="acoes" style="margin-top:10px"><button class="btn btn-sm btn-primary" id="set-salvar">Salvar set</button><button class="btn btn-sm" id="set-cancelar">Cancelar</button><span class="dica" id="set-msg"></span></div>`;
  preencherStats('set-stats', { titulo: s.titulo, itens: s.itens, consumiveis: s.consumiveis });
}
function abrirEditorSet(s) {
  SETED = { id: s ? s.id : null, titulo: s ? s.titulo : '', itens: s ? JSON.parse(JSON.stringify(s.itens)) : {}, consumiveis: s ? JSON.parse(JSON.stringify(s.consumiveis)) : [], voc: (s && s.voc) || vocEmUso(), sel: '' };
  $('sets-editor-box').style.display = '';
  desenharEditorSet();
  $('sets-editor-box').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  const arma = SETED.itens.arma;
  if (arma && arma.perks && arma.prof) {   // set já salvo com proficiência: carrega os ícones e as opções do Perk Shaping e redesenha
    const voc = SETED.voc || '';
    Promise.all([Object.keys(SET_ICONES).length ? null : api.set_icones_prof(), SET_SHAPING[voc] ? null : api.set_shaping(voc)]).then(([ic, sh]) => {
      if (ic) SET_ICONES = ic;
      if (sh) SET_SHAPING[voc] = sh;
      if (SETED) desenharEditorSet();
    });
  }
}
function lerCamposSet() {   // guarda o que foi digitado antes de redesenhar
  if (!$('set-titulo')) return;
  SETED.titulo = $('set-titulo').value;
  SETED.voc = $('set-voc').value;
}
// abre a lista de itens do espaço (slot "consumivel" = consumíveis) e devolve o item escolhido ou null
async function pedirItemSet(slot) {
  lerCamposSet();
  if (!SET_ITENS[slot]) {
    toast('Baixando a lista de itens da TibiaWiki (só na primeira vez, pode levar alguns segundos)...');
    SET_ITENS[slot] = (await api.set_itens(slot)) || [];
  }
  const voc = slot === 'consumivel' ? '' : SETED.voc;
  const lista = SET_ITENS[slot].filter((i) => !voc || (i.vocs || []).includes(voc));
  const opcoes = lista.map((i) => ({ valor: i, busca: i.nome,
    html: `${i.imagem ? `<img src="${esc(i.imagem)}" alt="" onerror="this.style.visibility='hidden'">` : ''}<span class="escolha-txt"><b>${esc(i.nome)}</b>
      <span class="dica">${esc(i.desc || '')}${i.level ? ` · level ${i.level}` : ''}${i.imbue ? ` · ${i.imbue} embuimento${i.imbue > 1 ? 's' : ''}` : ''}</span></span>` }));
  const it = await escolher(slot === 'consumivel' ? 'Escolha o consumível' : `Escolha: ${rotuloSlot(slot)}`, opcoes, { filtro: true,
    vazio: SET_ITENS[slot].length ? 'Nenhum item dessa vocação.' : 'Não consegui baixar a lista de itens. Confira a internet e tente de novo.' });
  if (!SET_ITENS[slot].length) delete SET_ITENS[slot];   // lista vazia = falhou: tenta de novo da próxima vez
  return it || null;
}
async function escolherItemSet(slot) {
  const it = await pedirItemSet(slot);
  if (!it) return;
  const anterior = SETED.itens[slot];
  SETED.itens[slot] = { nome: it.nome, imagem: it.imagem, desc: it.desc, imbue: it.imbue || 0, imbues: anterior && anterior.nome === it.nome ? anterior.imbues : [],
    armor: it.armor, defense: it.defense, attack: it.attack, attrib: it.attrib, resist: it.resist, atk_elem: it.atk_elem };
  SETED.sel = slot;
  if (slot === 'arma') await carregarPerksArma(anterior);
  desenharEditorSet();
}
async function adicionarConsumivel() {
  if (SETED.consumiveis.length >= SET_MAX_CONS) return toast(`No máximo ${SET_MAX_CONS} consumíveis.`, true);
  const it = await pedirItemSet('consumivel');
  if (!it) return;
  if (SETED.consumiveis.some((c) => c.nome === it.nome)) return toast('Esse consumível já está no set.', true);
  SETED.consumiveis.push({ nome: it.nome, imagem: it.imagem });
  desenharEditorSet();
}
$('sets-novo').addEventListener('click', () => { if (SET_TAB) abrirEditorSet(null); });
$('cfg-sets').addEventListener('click', async (e) => {
  const b = e.target.closest('[data-set-ver],[data-set-editar],[data-set-apagar],[data-set-cel],[data-set-trocar],[data-set-tirar],[data-set-cons-add],[data-set-cons-tirar],[data-set-perks],[data-prof-pick],[data-reshape],#set-salvar,#set-cancelar');
  if (!b) return;
  const d = b.dataset, achar = (id) => SETS.find((s) => s.id === id);
  if (d.setVer) return abrirVistaSet(achar(d.setVer));
  if (d.setEditar) return abrirEditorSet(achar(d.setEditar));
  if (d.setApagar) {
    const s = achar(d.setApagar);
    if (!s || !confirm(`Apagar o set "${s.titulo}"? As hunts que já usaram esse set continuam com os itens dele.`)) return;
    await api.set_remover(s.id);
    await montarSetsConfig();
    return;
  }
  if (d.setCel) {
    if (SETED.itens[d.setCel]) { lerCamposSet(); SETED.sel = d.setCel; return desenharEditorSet(); }
    return escolherItemSet(d.setCel);
  }
  if (d.setTrocar) return escolherItemSet(d.setTrocar);
  if (d.reshape !== undefined) { lerCamposSet(); return abrirReshape(+d.reshape); }
  if (d.profPick !== undefined) {
    lerCamposSet();
    const arma = SETED.itens.arma, [ci, oi] = d.profPick.split(':').map(Number);
    arma.prof.escolhas = Array.from({ length: arma.perks.length }, (_, k) => arma.prof.escolhas[k] || 0);
    arma.prof.escolhas[ci] = oi;
    return desenharEditorSet();
  }
  if (d.setPerks !== undefined) { lerCamposSet(); await carregarPerksArma(null); return desenharEditorSet(); }
  if (d.setTirar) { lerCamposSet(); delete SETED.itens[d.setTirar]; SETED.sel = ''; return desenharEditorSet(); }
  if (d.setConsAdd !== undefined) return adicionarConsumivel();
  if (d.setConsTirar !== undefined) { lerCamposSet(); SETED.consumiveis.splice(+d.setConsTirar, 1); return desenharEditorSet(); }
  if (b.id === 'set-cancelar') { SETED = null; $('sets-editor').innerHTML = ''; $('sets-editor-box').style.display = 'none'; return; }
  if (b.id === 'set-salvar') {
    lerCamposSet();
    const r = await api.set_salvar({ id: SETED.id, titulo: SETED.titulo, itens: SETED.itens, consumiveis: SETED.consumiveis, voc: SETED.voc });
    if (!r.ok) { $('set-msg').textContent = r.erro; return; }
    toast(`Set "${r.set.titulo}" salvo!`);
    SETED = null; $('sets-editor').innerHTML = ''; $('sets-editor-box').style.display = 'none';
    await montarSetsConfig();
  }
});
$('cfg-sets').addEventListener('change', async (e) => {
  const d = e.target.dataset, arma = SETED && SETED.itens.arma;
  const ehProf = ['profNivel', 'profMaestria', 'profCol', 'trocaCol', 'trocaOp', 'trocaRank'].some((k) => d[k] !== undefined);
  if (arma && arma.prof && ehProf) {
    lerCamposSet();
    const p = arma.prof;
    if (d.profNivel !== undefined) p.nivel = +e.target.value;
    if (d.profMaestria !== undefined) p.maestria = e.target.checked;
    if (d.profCol !== undefined) { p.escolhas = Array.from({ length: arma.perks.length }, (_, k) => p.escolhas[k] || 0); p.escolhas[+d.profCol] = +e.target.value; }
    for (const [campo, chave] of [['trocaCol', 'coluna'], ['trocaOp', 'opcao'], ['trocaRank', 'rank']]) {
      if (d[campo] === undefined) continue;
      const i = +d[campo];
      p.trocas = [p.trocas[0] || {}, p.trocas[1] || {}];
      p.trocas[i] = { coluna: 0, opcao: '', rank: 0, ...p.trocas[i], [chave]: chave === 'opcao' ? e.target.value : +e.target.value };
    }
    p.trocas = p.trocas.map((t) => (t && t.coluna && t.opcao ? t : (t && Object.keys(t).length ? t : {})));
    while (p.trocas.length && !p.trocas[p.trocas.length - 1].coluna && !p.trocas[p.trocas.length - 1].opcao) p.trocas.pop();
    return desenharEditorSet();
  }
  if (e.target.id === 'set-voc') {
    SETED.voc = e.target.value;
    if (!SET_SHAPING[SETED.voc]) SET_SHAPING[SETED.voc] = (await api.set_shaping(SETED.voc)) || [];
    desenharEditorSet();
    return;
  }
  const m = e.target.dataset.setImb;
  if (!m) return;
  lerCamposSet();
  const [slot, i] = m.split(':'), it = SETED.itens[slot];
  const imbues = Array.from({ length: it.imbue || 0 }, (_, k) => (it.imbues || [])[k] || '');   // uma posição por vaga
  imbues[+i] = e.target.value;
  if (e.target.value && imbues.filter((x) => x === e.target.value).length > 1) { imbues[+i] = ''; toast('Esse embuimento já está neste item.', true); }
  it.imbues = imbues.filter(Boolean);
  desenharEditorSet();
});

// ---------- o set dentro da hunt (seção "Seu personagem nesta hunt") ----------
// H.entrada.set: {titulo, itens, consumiveis} = escolhido; {} = sem set; null = hunt antiga com set não informado (não é enviado ao salvar)
function resumoSet() {
  const s = H.entrada.set;
  return s == null ? 'set não informado' : !s.itens ? 'sem set' : `Set: ${s.titulo}`;
}
function htmlSetHunt() {
  const s = H.entrada.set;
  const mesmo = (x) => x.titulo === s.titulo && JSON.stringify(x.itens) === JSON.stringify(s.itens) && JSON.stringify(x.consumiveis) === JSON.stringify(s.consumiveis);
  const sel = s && s.itens ? SETS.find(mesmo) : null;
  const opcoes = SETS.map((x) => `<option value="${esc(x.id)}" ${sel && sel.id === x.id ? 'selected' : ''}>${esc(x.titulo)}</option>`).join('');
  const guardado = s && s.itens && !sel ? `<option value="__hunt" selected>${esc(s.titulo)} (guardado nesta hunt)</option>` : '';
  return `<h3 class="sub3" style="margin-top:18px">Set de equipamento</h3>
    <div class="dica perso-desc">Escolha o conjunto de itens e embuimentos que você usou nesta hunt. Cadastre os seus em Configurações.</div>
    ${s == null ? '<div class="dica" style="margin:0 0 8px">Set não informado nesta hunt: escolha para marcar, ou <button class="btn btn-sm" data-marcar-vazio="set">Marcar sem set</button></div>' : ''}
    <div class="roda-linha"><select id="h-set-sel">${s == null ? '<option value="" selected disabled>Escolher o set...</option>' : ''}
      <option value="__nenhum" ${s && !s.itens ? 'selected' : ''}>Sem set</option>${opcoes}${guardado}</select>
      ${s && s.itens ? '<button class="btn btn-sm" data-set-hunt-ver>👁 Ver o set</button>' : ''}
      ${SETS.length ? '' : '<span class="dica">Nenhum set cadastrado: cadastre em Configurações.</span>'}</div>
    ${s && s.itens ? `<div class="set-hunt-foto">${htmlFotoSet(s, { mini: true })}</div>` : ''}
    <div id="h-combat"></div>${(setTimeout(atualizarCombatHunt, 0), '')}`;
}
$('h-res').addEventListener('change', (e) => {
  if (e.target.id !== 'h-set-sel') return;
  const v = e.target.value;
  if (v === '__hunt') return;                         // o set guardado na hunt já é o escolhido
  if (v === '__nenhum') H.entrada.set = {};
  else { const x = SETS.find((s) => s.id === v); if (x) H.entrada.set = { titulo: x.titulo, itens: x.itens, consumiveis: x.consumiveis, voc: x.voc }; }
  redesenharPerso();
});
$('h-res').addEventListener('click', (e) => {
  if (e.target.closest('[data-set-hunt-ver]') && H.entrada.set && H.entrada.set.itens) abrirVistaSet(H.entrada.set);
});
