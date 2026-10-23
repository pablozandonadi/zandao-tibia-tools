(function () {
  'use strict';
  // Admin: códigos de acesso ao menu Mensagens para clientes que pagam. O código gerado só existe na caixa de uso único (DOM): nada vai para storage nem variável global.
  const el = id => document.getElementById(id);
  const bridge = () => window.pywebview && window.pywebview.api;
  const GENERICO = 'Não foi possível concluir. Tente novamente.';
  let geracao = 0;
  const chamar = async f => { try { return await f(bridge()); } catch (e) { return {erro: GENERICO}; } };
  // Todo texto entra por textContent (os nomes de clientes vêm do usuário).
  function h(tag, props, ...filhos) {
    const e = document.createElement(tag);
    const {texto, onclick, ...resto} = props || {};
    if (texto !== undefined) e.textContent = texto;
    if (onclick) e.addEventListener('click', onclick);
    Object.assign(e, resto);
    e.append(...filhos);
    return e;
  }
  const data = s => s ? new Date(s * 1000).toLocaleDateString('pt-BR') : '—';
  const usosRestantes = c => c.uses === null ? 'Ilimitado' : `${c.uses} restante${c.uses === 1 ? '' : 's'}`;
  function aviso(texto) { const m = el('admin-msg-aviso'); if (m) m.textContent = texto || ''; return !!texto; }
  const mostrarErro = r => aviso(r && r.erro ? r.erro : '');

  function mostrarCodigo(cliente, codigo) {
    el('admin-msg-painel').replaceChildren(h('div', {className: 'card'},
      h('p', {texto: `Código de acesso de ${cliente}`}),
      h('code', {id: 'admin-msg-codigo', texto: codigo}),
      h('p', {className: 'dica', texto: 'Este código só aparece agora. Copie e envie ao cliente; depois de fechar não dá para vê-lo de novo.'}),
      h('button', {className: 'btn', texto: 'Copiar', onclick: () => { const falhou = () => aviso('Copie à mão.');
        try { navigator.clipboard.writeText(codigo).catch(falhou); } catch (e) { falhou(); } }}),
      h('button', {className: 'btn', texto: 'Fechar', onclick: () => el('admin-msg-painel').replaceChildren()})));
  }

  async function gerar(cliente, usos) {
    const r = await chamar(api => api.admin_msg_gerar(cliente, usos));
    if (mostrarErro(r)) return r;
    await carregar(); // redesenha a lista; a caixa do código vem depois, para não ser apagada
    mostrarCodigo(cliente, r.codigo);
    return r;
  }

  function formGerar() {
    const nome = h('input', {type: 'text', maxLength: 60, placeholder: 'Nome do cliente'});
    const usos = h('input', {type: 'number', min: 1, max: 1000, step: 1, value: 1});
    const form = h('form', {className: 'card'},
      h('h2', {texto: 'Gerar código de acesso ao menu Mensagens'}),
      h('label', {}, 'Cliente ', nome),
      h('label', {}, 'Quantos PCs podem usar este código ', usos),
      h('button', {className: 'btn btn-primary', type: 'submit', texto: 'Gerar'}));
    form.addEventListener('submit', event => {
      event.preventDefault();
      const n = Number(usos.value);
      if (!nome.value.trim()) { aviso('Informe o nome do cliente.'); return; }
      if (!Number.isInteger(n) || n < 1 || n > 1000) { aviso('Usos de 1 a 1000.'); return; }
      return gerar(nome.value.trim(), n);
    });
    return form;
  }

  async function revogar(c) {
    if (!confirm(`Revogar o código de ${c.note}? Quem ainda não usou não consegue mais ativar.`)) return;
    const r = await chamar(api => api.admin_msg_revogar(c.id));
    if (!mostrarErro(r)) await carregar();
  }
  async function remover(c) {
    if (!confirm(`Remover o acesso de ${c.note}? O menu Mensagens deixa de funcionar para essa conta.`)) return;
    const r = await chamar(api => api.admin_msg_remover_conta(c.owner));
    if (!mostrarErro(r)) await carregar();
  }

  const tabela = (cabecalho, linhas) => h('table', {className: 'tabela-itens'},
    h('thead', {}, h('tr', {}, ...cabecalho.map(texto => h('th', {texto})))), h('tbody', {}, ...linhas));
  const linhaCodigo = c => h('tr', {}, ...[c.note, usosRestantes(c), data(c.created)].map(texto => h('td', {texto})),
    h('td', {}, h('button', {className: 'btn', texto: 'Revogar', onclick: () => revogar(c)})));
  const linhaConta = c => h('tr', {}, ...[c.note, data(c.since), c.admin ? 'Administrador' : 'Cliente'].map(texto => h('td', {texto})),
    h('td', {}, ...(c.admin ? [] : [h('button', {className: 'btn', texto: 'Remover acesso', onclick: () => remover(c)})])));

  // dados: {codigos, contas, erro}. Redesenhar apaga qualquer código mostrado.
  function render(dados) {
    el('admin-msg-raiz').replaceChildren(
      h('h2', {texto: 'Acesso ao menu Mensagens (clientes)'}),
      h('p', {id: 'admin-msg-aviso', className: 'dica', texto: dados.erro || ''}),
      h('div', {id: 'admin-msg-painel'}),
      ...(dados.erro ? [] : [formGerar(),
        h('h3', {texto: 'Códigos gerados'}),
        tabela(['Cliente', 'Usos', 'Criado', ''], (dados.codigos || []).map(linhaCodigo)),
        h('h3', {texto: 'Contas liberadas'}),
        tabela(['Conta', 'Desde', 'Tipo', ''], (dados.contas || []).map(linhaConta))]));
  }

  async function carregar() {
    const api = bridge();
    if (!api || !el('admin-msg-raiz')) return;
    const g = ++geracao;
    let r;
    try { r = await api.admin_msg_listar(); } catch (e) { r = {erro: 'Não foi possível consultar o servidor.'}; }
    if (g !== geracao) return;
    render(r);
  }

  window.adminMensagensCarregar = carregar;
  if (typeof module !== 'undefined' && module.exports) module.exports = {render, gerar, carregar};
  if (window.addEventListener) window.addEventListener('pywebviewready', carregar);
  carregar();
})();
