(function () {
  'use strict';
  // Admin: abas da página e controle dos comandos dos bots (WhatsApp e assistente). Cada comando liga/desliga e pode ter um texto próprio;
  // {resposta} dentro do texto entra com a resposta automática. Todo texto entra por textContent/value (os textos vêm do usuário).
  const el = id => document.getElementById(id);
  const bridge = () => window.pywebview && window.pywebview.api;
  const GENERICO = 'Não foi possível concluir. Tente novamente.';
  const BOTS = [['whatsapp', 'Bot do WhatsApp (no grupo, com !)'], ['assistente', 'Bot do assistente tibiano (no app)']];
  const DICA = 'Vazio = resposta padrão. "Usar o texto padrão como base" mostra o modelo de hoje; mude o que quiser e use as variáveis para os dados que mudam. Texto sem variáveis vira uma resposta fixa. A prévia consulta os dados reais com o exemplo ao lado.';
  let geracao = 0;
  const chamar = async f => { try { return await f(bridge()); } catch (e) { return {erro: GENERICO}; } };
  function h(tag, props, ...filhos) {
    const e = document.createElement(tag);
    const {texto, onclick, ...resto} = props || {};
    if (texto !== undefined) e.textContent = texto;
    if (onclick) e.addEventListener('click', onclick);
    Object.assign(e, resto);
    e.append(...filhos);
    return e;
  }

  // ---- abas da página Admin ----
  const PAINEIS = {ia: 'admin-raiz', msg: 'admin-msg-raiz', cmd: 'admin-cmd-raiz'};
  function abrirAba(nome) {
    if (!PAINEIS[nome]) return;
    Object.entries(PAINEIS).forEach(([chave, id]) => { const painel = el(id); if (painel) painel.hidden = chave !== nome; });
    const barra = el('admin-abas');
    if (barra && barra.querySelectorAll) barra.querySelectorAll('[data-admin-aba]').forEach(a => a.classList.toggle('on', a.dataset.adminAba === nome));
  }
  function ligarAbas() {
    const barra = el('admin-abas');
    if (barra && barra.querySelectorAll) barra.querySelectorAll('[data-admin-aba]').forEach(a => a.addEventListener('click', () => abrirAba(a.dataset.adminAba)));
  }

  // ---- comandos ----
  function cartao(bot, c) {
    const ligado = h('input', {type: 'checkbox', checked: c.enabled});
    const texto = h('textarea', {style: 'width:100%;box-sizing:border-box', rows: 10, maxLength: 1500, placeholder: DICA, value: c.text || ''});
    const aviso = h('span', {className: 'dica'});
    const mostrar = t => { aviso.textContent = t; };
    const salvar = async () => {
      const r = await chamar(api => api.admin_cmd_salvar(bot, c.cmd, ligado.checked, texto.value));
      if (r && r.erro) { mostrar(r.erro); return; }
      mostrar('Salvo.');
    };
    const restaurar = async () => {
      const r = await chamar(api => api.admin_cmd_restaurar(bot, c.cmd));
      if (r && r.erro) { mostrar(r.erro); return; }
      ligado.checked = true; texto.value = ''; mostrar('Voltou ao padrão.');
    };
    const exemplo = h('input', {type: 'text', maxLength: 80, value: c.example || '', placeholder: 'Exemplo para a prévia'});
    const previa = h('pre', {className: 'dica', style: 'white-space:pre-wrap'});
    const inserir = nome => {  // a variável entra onde está o cursor
      const ini = typeof texto.selectionStart === 'number' ? texto.selectionStart : texto.value.length;
      const fim = typeof texto.selectionEnd === 'number' ? texto.selectionEnd : ini;
      texto.value = texto.value.slice(0, ini) + '{' + nome + '}' + texto.value.slice(fim);
    };
    const ver = async () => {
      previa.textContent = 'Consultando…';
      const r = await chamar(api => api.admin_cmd_previa(bot, c.cmd, texto.value, exemplo.value));
      previa.textContent = r && r.erro ? r.erro : r.texto;
    };
    return h('div', {className: 'card'},
      h('h3', {texto: c.label}),
      h('label', {style: 'display:block;margin:8px 0'}, ligado, ' Responde a este comando'),
      h('label', {style: 'display:block;margin:8px 0'}, 'Texto da resposta', h('br'), texto),
      h('div', {className: 'dica'}, 'Variáveis (clique para inserir): ', ...(c.vars || []).map(v => h('button', {className: 'btn', type: 'button', texto: '{' + v.name + '}', title: v.desc, onclick: () => inserir(v.name)}))),
      ...(c.default ? [h('button', {className: 'btn', type: 'button', texto: 'Usar o texto padrão como base', onclick: () => { texto.value = c.default; }})] : []),
      h('label', {style: 'display:block;margin:8px 0'}, 'Exemplo para a prévia ', exemplo),
      h('button', {className: 'btn', type: 'button', texto: 'Prévia', onclick: ver}),
      h('button', {className: 'btn btn-primary', type: 'button', texto: 'Salvar', onclick: salvar}),
      h('button', {className: 'btn', type: 'button', texto: 'Restaurar padrão', onclick: restaurar}),
      aviso, previa);
  }

  // dados: {bots: {whatsapp: [...], assistente: [...]}, erro}
  function render(dados) {
    const raiz = el('admin-cmd-raiz');
    if (!raiz) return;
    if (dados.erro) { raiz.replaceChildren(h('p', {id: 'admin-cmd-aviso', className: 'dica', texto: dados.erro})); return; }
    raiz.replaceChildren(h('p', {className: 'dica', texto: DICA}),
      ...BOTS.flatMap(([bot, titulo]) => [h('h2', {texto: titulo}), ...((dados.bots && dados.bots[bot]) || []).map(c => cartao(bot, c))]));
  }

  async function carregar() {
    const api = bridge();
    if (!api || !el('admin-cmd-raiz')) return;
    const g = ++geracao;
    let r;
    try { r = await api.admin_cmd_listar(); } catch (e) { r = {erro: 'Não foi possível consultar o servidor.'}; }
    if (g !== geracao) return;
    render(r);
  }

  window.adminComandosCarregar = carregar;
  if (typeof module !== 'undefined' && module.exports) module.exports = {render, carregar, abrirAba};
  if (window.addEventListener) window.addEventListener('pywebviewready', carregar);
  ligarAbas();
  carregar();
})();
