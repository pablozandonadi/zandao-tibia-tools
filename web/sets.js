// Character Sets: cadastro em Configurações (editor com os itens da TibiaWiki), escolha na hunt e janela "Ver set".
// Depende de index.html: $, esc, toast, api, H, escolher, redesenharPerso. Carregado depois do roda.js.

const SET_GRUPOS = [['Ataque', ['arma', 'anel', 'amuleto']], ['Defesa', ['cabeca', 'armadura', 'pernas', 'botas', 'mao']]];
let SETS = [];                 // sets cadastrados: [{id, titulo, itens, consumiveis}]
let SET_TAB = null;            // {slots: [[chave, rótulo]], embuimentos: [{nome, sub}]}
const SET_ITENS = {};          // itens da TibiaWiki por slot (baixados na 1ª vez que o slot é aberto)
const rotuloSlot = (k) => ((SET_TAB && SET_TAB.slots.find((s) => s[0] === k)) || [k, k])[1];

async function carregarSets() {
  SETS = (await api.set_listar()) || [];
  if (!SET_TAB) SET_TAB = await api.set_tabelas();
  return SETS;
}
// set da última hunt desse personagem (valor inicial de uma hunt nova); {} = sem set
const setInicial = async (personagem) => (await api.hunt_ultimo_set(personagem || '')) || {};

// ---------- a vista de um set (usada na janela "Ver set") ----------
const imgItem = (it) => (it.imagem ? `<img class="set-img" src="${esc(it.imagem)}" alt="" onerror="this.style.visibility='hidden'">` : '<span class="set-img"></span>');
function htmlItemSet(slot, it) {
  const imb = (it.imbues || []).map((e) => `<span class="chip chip-neutro" style="font-size:.64rem">${esc(e)}</span>`).join(' ');
  return `<div class="set-item">${imgItem(it)}<div class="set-item-txt"><small class="dim">${esc(rotuloSlot(slot))}</small><b>${esc(it.nome)}</b>
    ${it.desc ? `<span class="dica">${esc(it.desc)}</span>` : ''}${imb ? `<div>${imb}</div>` : ''}</div></div>`;
}
function htmlSetVista(s) {
  if (!s || !s.itens) return '<p class="dica">Sem set nesta hunt.</p>';
  const grupo = ([nome, slots]) => {
    const itens = slots.filter((k) => s.itens[k]);
    return `<div class="set-grupo"><h4>${nome}</h4>${itens.length ? itens.map((k) => htmlItemSet(k, s.itens[k])).join('') : '<p class="dica">Nada escolhido.</p>'}</div>`;
  };
  const cons = (s.consumiveis || []).length ? `<div class="set-grupo"><h4>Consumíveis</h4><div>${s.consumiveis.map((c) => `<span class="chip chip-neutro">${esc(c)}</span>`).join(' ')}</div></div>` : '';
  return `<div class="set-vista">${SET_GRUPOS.map(grupo).join('')}${cons}</div>`;
}
function abrirVistaSet(s) {
  $('set-vista-titulo').textContent = s && s.titulo ? s.titulo : 'Set';
  $('set-vista-corpo').innerHTML = htmlSetVista(s);
  $('modal-set').style.display = 'flex';
}
$('set-vista-fechar').addEventListener('click', () => { $('modal-set').style.display = 'none'; });
$('modal-set').addEventListener('click', (e) => { if (e.target === $('modal-set')) $('modal-set').style.display = 'none'; });

// ---------- Configurações: lista e editor ----------
let SETED = null;   // set em edição: {id|null, titulo, itens, consumiveis, voc}
const qtdItens = (s) => Object.keys(s.itens || {}).length;
function desenharSetsConfig() {
  $('sets-lista').innerHTML = SETS.length ? SETS.map((s) => `<div class="roda-item">
      <div class="roda-nome"><b>${esc(s.titulo)}</b> <span class="chip chip-neutro">${qtdItens(s)} ite${qtdItens(s) === 1 ? 'm' : 'ns'}</span></div>
      <div class="acoes"><button class="btn btn-sm" data-set-ver="${esc(s.id)}">👁 Ver</button><button class="btn btn-sm" data-set-editar="${esc(s.id)}">🛠 Editar</button>
        <button class="btn btn-sm btn-danger" data-set-apagar="${esc(s.id)}" title="Apagar">✕</button></div></div>`).join('')
    : '<div class="dica">Nenhum set cadastrado ainda.</div>';
}
async function montarSetsConfig() { await carregarSets(); desenharSetsConfig(); }

function desenharEditorSet() {
  const s = SETED, emb = SET_TAB.embuimentos;
  const slotHtml = ([k, rot]) => {
    const it = s.itens[k];
    if (!it) return `<div class="set-slot"><small class="dim">${esc(rot)}</small><button class="btn btn-sm" data-set-esc="${k}">+ Escolher item</button></div>`;
    const sel = Array.from({ length: it.imbue || 0 }, (_, i) => `<select data-set-imb="${k}:${i}"><option value="">— embuimento ${i + 1} —</option>
      ${emb.map((e) => `<option value="${esc(e.nome)}" ${(it.imbues || [])[i] === e.nome ? 'selected' : ''}>${esc(e.nome)}${e.sub ? ' (' + esc(e.sub) + ')' : ''}</option>`).join('')}</select>`).join('');
    return `<div class="set-slot ocupado"><div class="set-slot-topo"><small class="dim">${esc(rot)}</small>
        <span><button class="btn btn-sm" data-set-esc="${k}" title="Trocar o item">⇄</button><button class="btn btn-sm" data-set-tirar="${k}" title="Tirar o item">✕</button></span></div>
      <div class="set-item">${imgItem(it)}<div class="set-item-txt"><b>${esc(it.nome)}</b>${it.desc ? `<span class="dica">${esc(it.desc)}</span>` : ''}</div></div>
      ${sel || '<span class="dica">Este item não tem vaga de embuimento.</span>'}</div>`;
  };
  $('sets-editor').innerHTML = `<div class="roda-barra"><input type="text" id="set-titulo" placeholder="Nome do set (ex.: Tokyo - Elite Knight)" maxlength="60" value="${esc(s.titulo)}">
      <select id="set-voc" title="Mostra só os itens dessa vocação ao escolher"><option value="">Todas as vocações</option>
      ${['knight', 'paladin', 'sorcerer', 'druid', 'monk'].map((v) => `<option value="${v}" ${s.voc === v ? 'selected' : ''}>${v[0].toUpperCase() + v.slice(1)}</option>`).join('')}</select></div>
    <div class="set-grade">${SET_TAB.slots.map(slotHtml).join('')}</div>
    <label class="campo-label" for="set-cons">Consumíveis (separe por vírgula)</label>
    <input type="text" id="set-cons" placeholder="ex.: Ultimate Mana Potion, Supreme Health Potion" value="${esc((s.consumiveis || []).join(', '))}">
    <div class="acoes" style="margin-top:10px"><button class="btn btn-sm btn-primary" id="set-salvar">Salvar set</button><button class="btn btn-sm" id="set-cancelar">Cancelar</button><span class="dica" id="set-msg"></span></div>`;
}
function abrirEditorSet(s) {
  SETED = { id: s ? s.id : null, titulo: s ? s.titulo : '', itens: s ? JSON.parse(JSON.stringify(s.itens)) : {}, consumiveis: s ? [...s.consumiveis] : [], voc: '' };
  $('sets-editor-box').style.display = '';
  desenharEditorSet();
  $('sets-editor-box').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
function lerCamposSet() {   // guarda o que foi digitado antes de redesenhar
  if (!$('set-titulo')) return;
  SETED.titulo = $('set-titulo').value;
  SETED.voc = $('set-voc').value;
  SETED.consumiveis = $('set-cons').value.split(',').map((x) => x.trim()).filter(Boolean);
}
async function escolherItemSet(slot) {
  lerCamposSet();
  if (!SET_ITENS[slot]) {
    toast('Baixando a lista de itens da TibiaWiki (só na primeira vez, pode levar alguns segundos)...');
    SET_ITENS[slot] = (await api.set_itens(slot)) || [];
  }
  const voc = SETED.voc;
  const lista = SET_ITENS[slot].filter((i) => !voc || (i.vocs || []).includes(voc));
  const opcoes = lista.map((i) => ({ valor: i, busca: i.nome,
    html: `${i.imagem ? `<img src="${esc(i.imagem)}" alt="" onerror="this.style.visibility='hidden'">` : ''}<span class="escolha-txt"><b>${esc(i.nome)}</b>
      <span class="dica">${esc(i.desc || '')}${i.level ? ` · level ${i.level}` : ''}${i.imbue ? ` · ${i.imbue} embuimento${i.imbue > 1 ? 's' : ''}` : ''}</span></span>` }));
  const it = await escolher(`Escolha: ${rotuloSlot(slot)}`, opcoes, { filtro: true,
    vazio: SET_ITENS[slot].length ? 'Nenhum item dessa vocação.' : 'Não consegui baixar a lista de itens. Confira a internet e tente de novo.' });
  if (!SET_ITENS[slot].length) delete SET_ITENS[slot];   // lista vazia = falhou: tenta de novo da próxima vez
  if (!it) return;
  const anterior = SETED.itens[slot];
  SETED.itens[slot] = { nome: it.nome, imagem: it.imagem, desc: it.desc, imbue: it.imbue || 0, imbues: anterior && anterior.nome === it.nome ? anterior.imbues : [],
    armor: it.armor, defense: it.defense, attack: it.attack, attrib: it.attrib, resist: it.resist, atk_elem: it.atk_elem };
  desenharEditorSet();
}
$('sets-novo').addEventListener('click', () => { if (SET_TAB) abrirEditorSet(null); });
$('cfg-sets').addEventListener('click', async (e) => {
  const b = e.target.closest('[data-set-ver],[data-set-editar],[data-set-apagar],[data-set-esc],[data-set-tirar],#set-salvar,#set-cancelar');
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
  if (d.setEsc) return escolherItemSet(d.setEsc);
  if (d.setTirar) { lerCamposSet(); delete SETED.itens[d.setTirar]; return desenharEditorSet(); }
  if (b.id === 'set-cancelar') { SETED = null; $('sets-editor').innerHTML = ''; $('sets-editor-box').style.display = 'none'; return; }
  if (b.id === 'set-salvar') {
    lerCamposSet();
    const r = await api.set_salvar({ id: SETED.id, titulo: SETED.titulo, itens: SETED.itens, consumiveis: SETED.consumiveis });
    if (!r.ok) { $('set-msg').textContent = r.erro; return; }
    toast(`Set "${r.set.titulo}" salvo!`);
    SETED = null; $('sets-editor').innerHTML = ''; $('sets-editor-box').style.display = 'none';
    await montarSetsConfig();
  }
});
$('cfg-sets').addEventListener('change', (e) => {
  if (e.target.id === 'set-voc') { SETED.voc = e.target.value; return; }
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
  const sel = s && s.itens ? SETS.find((x) => x.titulo === s.titulo && JSON.stringify(x.itens) === JSON.stringify(s.itens)) : null;
  const opcoes = SETS.map((x) => `<option value="${esc(x.id)}" ${sel && sel.id === x.id ? 'selected' : ''}>${esc(x.titulo)}</option>`).join('');
  const guardado = s && s.itens && !sel ? `<option value="__hunt" selected>${esc(s.titulo)} (guardado nesta hunt)</option>` : '';
  return `<h3 class="sub3" style="margin-top:18px">Set de equipamento</h3>
    <div class="dica perso-desc">Escolha o conjunto de itens e embuimentos que você usou nesta hunt. Cadastre os seus em Configurações.</div>
    ${s == null ? '<div class="dica" style="margin:0 0 8px">Set não informado nesta hunt: escolha para marcar, ou <button class="btn btn-sm" data-marcar-vazio="set">Marcar sem set</button></div>' : ''}
    <div class="roda-linha"><select id="h-set-sel">${s == null ? '<option value="" selected disabled>Escolher o set...</option>' : ''}
      <option value="__nenhum" ${s && !s.itens ? 'selected' : ''}>Sem set</option>${opcoes}${guardado}</select>
      ${s && s.itens ? '<button class="btn btn-sm" data-set-hunt-ver>👁 Ver o set</button>' : ''}
      ${SETS.length ? '' : '<span class="dica">Nenhum set cadastrado: cadastre em Configurações.</span>'}</div>`;
}
$('h-res').addEventListener('change', (e) => {
  if (e.target.id !== 'h-set-sel') return;
  const v = e.target.value;
  if (v === '__hunt') return;                         // o set guardado na hunt já é o escolhido
  if (v === '__nenhum') H.entrada.set = {};
  else { const x = SETS.find((s) => s.id === v); if (x) H.entrada.set = { titulo: x.titulo, itens: x.itens, consumiveis: x.consumiveis }; }
  redesenharPerso();
});
$('h-res').addEventListener('click', (e) => {
  if (e.target.closest('[data-set-hunt-ver]') && H.entrada.set && H.entrada.set.itens) abrirVistaSet(H.entrada.set);
});
