/* Mirror: controles de perfis e recortes; a captura pertence ao motor nativo. */
(function (global) {
  'use strict';
  const escape = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const color = value => /^#[0-9a-f]{6}$/i.test(String(value)) ? value : '#ff6b3d';
  const clamp = (value, min, max, fallback) => Number.isFinite(Number(value)) ? Math.max(min, Math.min(max, Number(value))) : fallback;
  function normalize(data) {
    return {personagem: data.personagem || '', perfis: Array.isArray(data.perfis) ? data.perfis : [], ativo: data.ativo || '', perfil: data.perfil || null, estado: data.estado || {}, clientes: Array.isArray(data.clientes) ? data.clientes : []};
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {escape, color, clamp, normalize};
  if (!global.document) return;
  const bridge = () => global.pywebview && global.pywebview.api;
  let state = normalize({}), generation = 0, chain = Promise.resolve(), busy = false, pending = false, message = '', formAction = '';
  const root = () => document.getElementById('mirror-root');
  const button = (text, action, disabled, extra = '') => `<button type="button" class="btn btn-sm ${extra}" data-action="${action}" ${disabled ? 'disabled' : ''}>${text}</button>`;
  const checked = value => value ? 'checked' : '';
  const selectionPending = data => !!(data.pending || data.pendente || data.estado && (data.estado.selecionando || data.estado.selecao_pendente || ['selecionando','aguardando_foco'].includes(data.estado.estado)));
  function render() {
    const host = root(); if (!host) return;
    const demo = !bridge(), has = !!state.personagem, profile = state.perfil, enabled = has && !!profile && !busy && !pending && !demo;
    const status = state.estado;
    const statusLabels = {ativo:'Mirrors ativos no Tibia.', oculto:'Mirrors ocultos: volte ao cliente Tibia para exibir.', pausado:'Layout alterado. Edite os recortes pausados para reposicionar.', sem_cliente:'Vincule o cliente Tibia para iniciar.', aguardando_foco:'Coloque o Tibia vinculado em primeiro plano para selecionar.', selecionando:'Seleção em andamento. Esc cancela.', erro:'O motor Mirror encontrou um erro.'};
    const nativeMessage = status.erro || status.mensagem || status.motivo || statusLabels[status.estado] || (status.vinculado || status.hwnd ? 'Cliente vinculado. Os mirrors aparecem com o Tibia em primeiro plano.' : 'Vincule o cliente Tibia para iniciar.');
    host.innerHTML = `<div class="mirror-head"><div><h1>Mirror</h1><p>Seus itens e atalhos do Tibia, sempre à vista.</p></div><span class="mirror-character">${escape(state.personagem || 'Nenhum personagem em uso')}</span></div>
      <div class="mirror-notice" role="status" aria-live="polite">${escape(message || (demo ? 'Prévia da interface. Abra o aplicativo para usar a captura ao vivo.' : pending ? 'Seleção em andamento: coloque o Tibia em primeiro plano. Quadrado: clique para confirmar. Manual: arraste e pressione Enter. Esc cancela.' : !has ? 'Selecione um personagem em uso na seção Personagens para configurar seus mirrors.' : nativeMessage))}</div>
      <div class="card mirror-config"><div class="mirror-row"><label class="mirror-field mirror-grow">Perfil<select data-field="profile" ${!has || busy || pending || demo ? 'disabled' : ''}><option value="">${state.perfis.length ? 'Selecione um perfil' : 'Nenhum perfil criado'}</option>${state.perfis.map(p => `<option value="${escape(p.id)}" ${p.id === state.ativo ? 'selected' : ''}>${escape(p.nome)}</option>`).join('')}</select></label><div class="mirror-actions">${button('Novo perfil','novo',!has || busy || pending || demo)}${button('Duplicar','duplicar',!enabled)}${button('Renomear','renomear',!enabled)}${button('Remover perfil','remover-perfil',!enabled)}</div></div>
      ${formAction ? `<form class="mirror-row mirror-profile-form"><label class="mirror-field mirror-grow">${formAction === 'novo' ? 'Nome do novo perfil' : formAction === 'duplicar' ? 'Nome da cópia' : 'Novo nome'}<input name="nome" type="text" maxlength="80" required value="${escape(formAction === 'renomear' ? profile.nome : formAction === 'duplicar' ? profile.nome + ' (cópia)' : '')}"></label><button class="btn btn-sm btn-primary" type="submit">Salvar</button>${button('Cancelar','cancelar-form',false)}</form>` : ''}
      <div class="mirror-row"><label class="mirror-field mirror-grow">Cliente Tibia<select data-field="client" ${!has || busy || pending || demo ? 'disabled' : ''}><option value="">Vincular cliente…</option>${state.clientes.map(c => `<option value="${escape(c.hwnd)}" ${String(c.hwnd) === String(status.hwnd || status.cliente_hwnd) ? 'selected' : ''}>${escape(c.titulo || 'Tibia')} · ${escape(c.hwnd)}</option>`).join('')}</select></label>${button('Atualizar clientes','reload',busy || pending || demo)}</div></div>
      <div class="mirror-row mirror-create">${pending ? button('Cancelar seleção','cancelar-selecao',demo) : ''}${button('＋ Quadrado 32 × 32','quadrado',!enabled,'btn-primary')}${button('＋ Seleção manual','manual',!enabled)}<span>Os dois modos têm lupa. No quadrado, a roda ajusta o tamanho.</span></div>
      <div class="mirror-row mirror-list-head"><h2>${escape(profile ? profile.nome : 'Recortes')} <small>${profile && profile.recortes ? profile.recortes.length : 0}</small></h2><div class="mirror-actions">${button('Mostrar todos','mostrar',!enabled)}${button('Ocultar todos','ocultar',!enabled)}${button('Travar todos','travar',!enabled)}${button('Destravar todos','destravar',!enabled)}</div></div>
      <div class="mirror-crops">${profile && profile.recortes && profile.recortes.length ? profile.recortes.map(r => crop(r,enabled)).join('') : `<div class="mirror-empty"><b>${has ? 'Seu próximo recorte começa aqui' : 'Mirror acompanha o personagem em uso'}</b><p>${has ? 'Crie um perfil, vincule o cliente e selecione um quadrado ou uma região do Tibia.' : 'Cada personagem mantém seus próprios perfis e recortes.'}</p></div>`}</div>
      <p class="mirror-foot">Use Posicionar, volte ao Tibia e arraste o recorte. Depois use Travar posição para o mouse passar pelo mirror. Alt+Tab, minimizar ou fechar o cliente oculta imagem, nome e glow. Se o layout mudar, use Editar recorte.</p>`;
  }
  function crop(r, enabled) {
    const glow = r.glow || {}, intensity = ['off','min','med','max'].includes(glow.intensidade) ? glow.intensidade : 'off';
    const disabled = enabled ? '' : 'disabled';
    const paused = (state.estado.recortes_pausados || []).includes(r.id);
    return `<article class="card mirror-crop" data-id="${escape(r.id)}"><div class="mirror-crop-top"><label class="mirror-field mirror-grow">Nome<input type="text" maxlength="80" data-field="nome" value="${escape(r.nome)}" ${disabled}></label><div class="mirror-sample" style="--mirror-color:${color(glow.cor)}" data-glow="${intensity}" aria-label="Prévia ilustrativa do glow"><span>32</span></div></div><p class="mirror-geometry">${paused ? '<strong class="mirror-paused">Reposicionar recorte · </strong>' : ''}${r.modo === 'manual' ? 'Manual' : 'Quadrado'} · ${escape((r.origem || {}).w)} × ${escape((r.origem || {}).h)} px de origem · x ${escape((r.origem || {}).x)}, y ${escape((r.origem || {}).y)}</p>
      <div class="mirror-toggles"><label><input type="checkbox" data-field="visivel" ${checked(r.visivel)} ${disabled}> Visível</label><label><input type="checkbox" data-field="travado" ${checked(r.travado)} ${disabled}> Travado</label><label><input type="checkbox" data-field="mostrar_nome" ${checked(r.mostrar_nome)} ${disabled}> Mostrar nome</label></div>
      <div class="mirror-controls"><label class="mirror-field">Escala de exibição<input type="number" min="0.25" max="8" step="0.25" data-field="escala" value="${clamp(r.escala,.25,8,1)}" ${disabled}></label><label class="mirror-field">Opacidade (${Math.round(clamp(r.opacidade,0,1,1)*100)}%)<input type="range" min="0.1" max="1" step="0.05" data-field="opacidade" value="${clamp(r.opacidade,.1,1,1)}" ${disabled}></label><label class="mirror-field">Glow<select data-field="intensidade" ${disabled}>${[['off','Desligado'],['min','Mínimo'],['med','Médio'],['max','Máximo']].map(([v,t]) => `<option value="${v}" ${v === intensity ? 'selected' : ''}>${t}</option>`).join('')}</select></label><label class="mirror-field">Cor livre<div class="mirror-color"><input type="color" data-field="cor" value="${color(glow.cor)}" ${disabled}><input type="text" aria-label="Cor hexadecimal do glow" data-field="hex" value="${color(glow.cor)}" pattern="#[0-9a-fA-F]{6}" maxlength="7" ${disabled}></div></label></div>
      <div class="mirror-row mirror-crop-footer"><span>A escala amplia a saída e preserva a origem.</span>${button(r.travado ? 'Posicionar' : 'Travar posição','posicionar',!enabled)}${button('Editar recorte','editar',!enabled)}${button('Remover','remover-recorte',!enabled)}</div></article>`;
  }
  async function load() {
    const gen = ++generation; pending = false; busy = false; message = ''; formAction = ''; state = normalize({}); render();
    if (!bridge()) return;
    try { const data = await bridge().mirror_carregar(); if (gen !== generation) return; if (data.erro) throw new Error(data.erro); state = normalize(data); pending = selectionPending(data); render(); }
    catch (error) { if (gen === generation) { message = error.message || 'Não foi possível carregar Mirror.'; render(); } }
  }
  function mutate(method,args) {
    const gen = generation;
    busy = true; message = ''; render();
    chain = chain.catch(() => {}).then(async () => {
      if (gen !== generation || !bridge()) return;
      try { const data = await bridge()[method](...args); if (gen !== generation) return; if (data.erro) throw new Error(data.erro); if (data.cancelado) pending = false; else if (selectionPending(data)) pending = true; if ('personagem' in data) { state = normalize(data); pending = selectionPending(data); } }
      catch (error) { if (gen === generation) message = error.message || 'Não foi possível concluir a ação.'; }
      finally { if (gen === generation) { busy = false; render(); } }
    });
    return chain;
  }
  document.addEventListener('click', event => {
    const host = root(), target = event.target.closest('[data-action]'); if (!host || !target || !host.contains(target) || target.disabled) return;
    const action = target.dataset.action, article = target.closest('[data-id]'), id = article ? article.dataset.id : '';
    if (action === 'reload') return load();
    if (action === 'cancelar-selecao') return mutate('mirror_cancelar',[]);
    if (['novo','duplicar','renomear'].includes(action)) { formAction = action; render(); const input = host.querySelector('[name="nome"]'); if (input) { input.focus(); input.select(); } return; }
    if (action === 'cancelar-form') { formAction = ''; render(); return; }
    if (action === 'remover-perfil') { if (global.confirm('Remover este perfil e seus recortes?')) mutate('mirror_perfil',['remover',state.ativo]); return; }
    if (['quadrado','manual','editar'].includes(action)) { const r = state.perfil && state.perfil.recortes.find(r => r.id === id); mutate('mirror_selecionar',[r ? r.modo : action,id]); return; }
    if (action === 'posicionar') { const r = state.perfil && state.perfil.recortes.find(r => r.id === id); if (r) mutate('mirror_recorte',['salvar',id,{travado:!r.travado}]); return; }
    if (action === 'remover-recorte') { if (global.confirm('Remover este recorte?')) mutate('mirror_recorte',['remover',id]); return; }
    if (['mostrar','ocultar','travar','destravar'].includes(action)) mutate('mirror_todos',[action]);
  });
  document.addEventListener('submit', event => {
    if (!root() || !root().contains(event.target) || !event.target.matches('.mirror-profile-form')) return;
    event.preventDefault(); const name = event.target.elements.nome.value.trim(); if (!name) return;
    const action = formAction; formAction = ''; mutate('mirror_perfil',[action,action === 'novo' ? '' : state.ativo,name]);
  });
  document.addEventListener('change', event => {
    const host = root(), input = event.target; if (!host || !host.contains(input) || !input.dataset.field || input.disabled) return;
    const field = input.dataset.field;
    if (field === 'profile') { if (input.value) mutate('mirror_perfil',['usar',input.value]); return; }
    if (field === 'client') { if (input.value) mutate('mirror_vincular',[Number(input.value)]); return; }
    const article = input.closest('[data-id]'), original = state.perfil && state.perfil.recortes.find(r => r.id === article.dataset.id); if (!original) return;
    const data = {...original, glow:{...original.glow}};
    if (['cor','hex'].includes(field)) { if (!/^#[0-9a-f]{6}$/i.test(input.value)) { message = 'Use uma cor hexadecimal com seis dígitos, como #ff6b3d.'; render(); return; } data.glow.cor = input.value; }
    else if (field === 'intensidade') data.glow.intensidade = input.value;
    else data[field] = input.type === 'checkbox' ? input.checked : ['escala','opacidade'].includes(field) ? Number(input.value) : input.value.trim();
    mutate('mirror_recorte',['salvar',original.id,data]);
  });
  global.addEventListener('mirrorEstado', event => {
    const data = event.detail; if (!data) return;
    if (data.personagem !== undefined && String(data.personagem || '') !== String(state.personagem || '')) return;
    if (data.perfis) state = normalize(data); else state.estado = {...state.estado,...(data.estado || data)};
    pending = data.cancelado ? false : selectionPending(data); message = data.erro || ''; render();
  });
  // API._emit invokes a global callback; feed the existing event-based renderer.
  global.mirrorEstado = data => global.dispatchEvent(new global.CustomEvent('mirrorEstado', {detail:data}));
  global.mirrorLoad = load;
})(typeof window !== 'undefined' ? window : globalThis);



