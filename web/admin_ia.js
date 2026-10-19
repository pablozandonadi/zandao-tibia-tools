(function () {
  'use strict';
  // Página Admin (só Beta): códigos da IA. O código gerado só existe na caixa de uso único (DOM): nada vai para storage nem variável global.
  const el = id => document.getElementById(id);
  const bridge = () => window.pywebview && window.pywebview.api;
  const AVISO_ILIMITADO = 'Ilimitado ainda respeita o teto global diário do servidor.';
  const MODOS = [['unlimited', 'Ilimitado'], ['daily', 'N por dia'], ['total', 'N no total']];
  const PLANO = Object.fromEntries(MODOS);
  let geracao = 0;
  // Todo texto entra por textContent (os nomes vêm do usuário).
  function h(tag, props, ...filhos) {
    const e = document.createElement(tag);
    const {texto, onclick, ...resto} = props || {};
    if (texto !== undefined) e.textContent = texto;
    if (onclick) e.addEventListener('click', onclick);
    Object.assign(e, resto);
    e.append(...filhos);
    return e;
  }
  const data = ms => ms ? new Date(ms).toLocaleDateString('pt-BR') : '—';
  const fimDoDia = v => v ? new Date(v + 'T23:59:59').getTime() : null;
  function uso(t) {
    if (t.mode === 'daily') return `${t.today_requests} de ${t.quota} hoje`;
    if (t.mode === 'total') return `${t.used_total} de ${t.quota} no total`;
    return `${t.today_requests} hoje`;
  }
  const situacao = t => t.revoked ? 'Revogado' : t.expires && t.expires <= Date.now() ? 'Vencido' : 'Ativo';

  // Limite (Ilimitado / N por dia / N no total) compartilhado pelo Gerar e pelo Alterar limite; "Zerar pacote" só ao alterar um plano total.
  function controlesLimite(atual) {
    const modo = h('select', {}, ...MODOS.map(([valor, texto]) => h('option', {value: valor, texto})));
    modo.value = atual ? atual.mode : 'daily';
    const qtd = h('input', {type: 'number', min: 1, step: 1, value: atual && atual.quota || ''});
    const aviso = h('p', {className: 'dica', texto: AVISO_ILIMITADO});
    const zerar = h('input', {type: 'checkbox'});
    const zerarRotulo = h('label', {}, zerar, ' Zerar pacote');
    const atualizar = () => {
      qtd.hidden = aviso.hidden = true;
      if (modo.value === 'unlimited') aviso.hidden = false; else qtd.hidden = false;
      zerarRotulo.hidden = !(atual && modo.value === 'total');
    };
    modo.addEventListener('change', atualizar);
    atualizar();
    return {
      el: h('div', {}, modo, qtd, zerarRotulo, aviso),
      valores: () => ({mode: modo.value, quota: modo.value === 'unlimited' ? null : Number(qtd.value), zerar: !zerarRotulo.hidden && zerar.checked})
    };
  }

  function mostrarErro(r) { el('admin-msg').textContent = r && r.erro ? r.erro : ''; return !!(r && r.erro); }
  const fecharPainel = () => el('admin-painel').replaceChildren();

  function mostrarCodigo(nome, token) {
    el('admin-painel').replaceChildren(h('div', {className: 'card'},
      h('p', {texto: `Código de ${nome}`}),
      h('code', {id: 'admin-codigo', texto: token}),
      h('p', {className: 'dica', texto: 'Este código só aparece agora. Copie e envie; depois de fechar não dá para vê-lo de novo.'}),
      h('button', {className: 'btn', texto: 'Copiar', onclick: () => { try { navigator.clipboard.writeText(token); } catch (e) { /* copia à mão */ } }}),
      h('button', {className: 'btn', texto: 'Fechar', onclick: fecharPainel})));
  }

  async function gerar(subject, mode, quota, expires) {
    const r = await bridge().admin_ia_gerar(subject, mode, quota, expires);
    if (mostrarErro(r)) return r;
    await carregar(); // redesenha a lista; a caixa do código vem depois, para não ser apagada
    mostrarCodigo(subject, r.token);
    return r;
  }

  function formGerar() {
    const nome = h('input', {type: 'text', maxLength: 64, placeholder: 'Nome'});
    const limite = controlesLimite();
    const validade = h('input', {type: 'date'});
    const form = h('form', {className: 'card'},
      h('h2', {texto: 'Gerar código'}),
      h('label', {}, 'Nome ', nome),
      h('label', {}, 'Limite de uso ', limite.el),
      h('label', {}, 'Validade (opcional) ', validade),
      h('button', {className: 'btn btn-primary', type: 'submit', texto: 'Gerar'}));
    form.addEventListener('submit', event => {
      event.preventDefault();
      const v = limite.valores();
      return gerar(nome.value.trim(), v.mode, v.quota, fimDoDia(validade.value));
    });
    return form;
  }

  function editarLimite(t) {
    const limite = controlesLimite(t);
    const validade = h('input', {type: 'date'});
    el('admin-painel').replaceChildren(h('div', {className: 'card'},
      h('p', {texto: `Alterar limite de ${t.subject}`}), limite.el,
      h('label', {}, 'Validade (opcional) ', validade),
      h('button', {className: 'btn btn-primary', texto: 'Salvar', onclick: async () => {
        const v = limite.valores();
        const r = await bridge().admin_ia_limite(t.subject, v.mode, v.quota, fimDoDia(validade.value), v.zerar);
        if (!mostrarErro(r)) await carregar();
      }}),
      h('button', {className: 'btn', texto: 'Cancelar', onclick: fecharPainel})));
  }

  async function revogar(t) {
    if (!confirm(`Revogar o código de ${t.subject}? Ele deixa de funcionar na hora.`)) return;
    const r = await bridge().admin_ia_revogar(t.subject);
    if (!mostrarErro(r)) await carregar();
  }

  function formSenha() {
    const campo = h('input', {type: 'password', autocomplete: 'off', placeholder: 'Senha de administrador'});
    const form = h('form', {className: 'card'},
      h('label', {}, 'Senha de administrador ', campo),
      h('button', {className: 'btn btn-primary', type: 'submit', texto: 'Salvar'}));
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const senha = campo.value;
      campo.value = '';
      if (!mostrarErro(await bridge().admin_ia_salvar_senha(senha))) await carregar();
    });
    return form;
  }

  function linha(t) {
    const acoes = t.revoked ? [] : [
      h('button', {className: 'btn', texto: 'Alterar limite', onclick: () => editarLimite(t)}),
      h('button', {className: 'btn', texto: 'Revogar', onclick: () => revogar(t)})];
    const celulas = [t.subject, PLANO[t.mode] || t.mode, uso(t), data(t.created), String(t.devices ?? 0), data(t.last_seen), situacao(t)];
    return h('tr', {}, ...celulas.map(texto => h('td', {texto})), h('td', {}, ...acoes));
  }

  // dados: {senha, tokens, erro}. Redesenhar apaga qualquer código mostrado.
  function render(dados) {
    const msg = h('p', {id: 'admin-msg', className: 'dica', texto: dados.erro || ''});
    const painel = h('div', {id: 'admin-painel'});
    if (!dados.senha) { el('admin-raiz').replaceChildren(msg, painel, formSenha()); return; }
    el('admin-raiz').replaceChildren(msg, painel, formGerar(),
      h('table', {className: 'tabela-itens'},
        h('thead', {}, h('tr', {}, ...['Nome', 'Plano', 'Uso', 'Criado', 'PCs', 'Último uso', 'Situação', ''].map(texto => h('th', {texto})))),
        h('tbody', {}, ...(dados.tokens || []).map(linha))),
      h('button', {className: 'btn', texto: 'Trocar senha', onclick: () => painel.replaceChildren(formSenha())}));
  }

  async function carregar() {
    const api = bridge();
    if (!api) return;
    const g = ++geracao;
    let estado, r;
    try { estado = await api.admin_ia_estado(); } catch (e) { return; }
    if (g !== geracao) return;
    el('admin-menu').hidden = !estado.beta;
    if (!estado.beta) return;
    if (!estado.senha) { render({senha: false}); return; }
    try { r = await api.admin_ia_listar(); } catch (e) { r = {erro: 'Não foi possível consultar o servidor.'}; }
    if (g !== geracao) return;
    render({senha: true, tokens: r.tokens, erro: r.erro});
  }

  window.adminIaCarregar = carregar;
  if (typeof module !== 'undefined' && module.exports) module.exports = {render, gerar, carregar, uso};
  if (window.addEventListener) window.addEventListener('pywebviewready', carregar);
  carregar();
})();
