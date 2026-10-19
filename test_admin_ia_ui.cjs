const assert = require('node:assert/strict');

class Element {
  constructor(tag = 'div') { this.tagName = tag; this.children = []; this.listeners = {}; this.className = ''; this.textContent = ''; this.value = ''; this.hidden = false; this.checked = false; }
  set innerHTML(value) { throw new Error('A página Admin nunca usa HTML'); }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
}
const raiz = new Element(), menu = new Element();
menu.hidden = true;
const achar = (no, teste) => { if (typeof no === 'string') return null; if (teste(no)) return no; for (const c of no.children) { const r = achar(c, teste); if (r) return r; } return null; };
const todos = (no, teste, acc = []) => { if (typeof no === 'string') return acc; if (teste(no)) acc.push(no); no.children.forEach(c => todos(c, teste, acc)); return acc; };
const texto = no => typeof no === 'string' ? no : no.textContent + no.children.map(texto).join('');
global.document = {
  createElement: tag => new Element(tag),
  getElementById: id => id === 'admin-raiz' ? raiz : id === 'admin-menu' ? menu : achar(raiz, n => n.id === id)
};
let estado = {beta: false, senha: false}, tokens = [], chamadas = [], confirmou = true;
global.confirm = () => confirmou;
global.window = {addEventListener() {}, pywebview: {api: {
  async admin_ia_estado() { return estado; },
  async admin_ia_listar() { return {tokens}; },
  async admin_ia_salvar_senha(s) { chamadas.push(['senha', s]); estado = {beta: true, senha: true}; return {ok: true}; },
  async admin_ia_gerar(...a) { chamadas.push(['gerar', ...a]); return {subject: a[0], token: 'ZT-CODIGO-FICTICIO'}; },
  async admin_ia_limite(...a) { chamadas.push(['limite', ...a]); return {ok: true}; },
  async admin_ia_revogar(s) { chamadas.push(['revogar', s]); return {ok: true}; }
}}};
global.localStorage = {setItem() { throw new Error('nada de storage'); }};
global.sessionStorage = global.localStorage;
const ui = require('./web/admin_ia.js');
const flush = () => new Promise(r => setImmediate(r));
const botao = (rotulo, base = raiz) => achar(base, n => n.tagName === 'button' && n.textContent === rotulo);

(async () => {
  await flush();
  assert.equal(menu.hidden, true, 'Fora do Beta a aba fica oculta');

  // Beta sem senha: só o campo de senha.
  estado = {beta: true, senha: false};
  await ui.carregar();
  assert.equal(menu.hidden, false);
  assert.ok(achar(raiz, n => n.type === 'password'));
  assert.equal(achar(raiz, n => n.tagName === 'table'), null, 'Sem senha não há tabela');
  assert.equal(botao('Gerar'), null);
  const campo = achar(raiz, n => n.type === 'password');
  campo.value = 'senha-ficticia';
  await achar(raiz, n => n.tagName === 'form').listeners.submit({preventDefault() {}});
  assert.deepEqual(chamadas.pop(), ['senha', 'senha-ficticia']);
  assert.equal(campo.value, '', 'O campo é limpo depois de salvar');

  // Com senha: tabela com o uso no formato de cada plano; HTML do nome não é interpretado.
  const ataque = '<img src=x onerror=alert(1)>';
  tokens = [
    {subject: ataque, mode: 'daily', quota: 50, today_requests: 12, used_total: 99, created: 1, revoked: 0, devices: 1, last_seen: null},
    {subject: 'bia', mode: 'total', quota: 100, today_requests: 3, used_total: 30, created: 1, revoked: 0, devices: 2, last_seen: 5},
    {subject: 'caio', mode: 'unlimited', quota: null, today_requests: 47, used_total: 500, created: 1, revoked: 0, devices: 0, last_seen: null}
  ];
  await ui.carregar();
  const linhas = todos(raiz, n => n.tagName === 'tr').slice(1);
  assert.equal(linhas.length, 3);
  assert.equal(linhas[0].children[0].textContent, ataque);
  assert.deepEqual(linhas.map(l => l.children[2].textContent), ['12 de 50 hoje', '30 de 100 no total', '47 hoje']);
  assert.ok(botao('Trocar senha'));

  // Gerar: o código aparece uma vez, na caixa, e some ao fechar ou ao redesenhar.
  const selecoes = todos(raiz, n => n.tagName === 'select');
  const formGerar = achar(raiz, n => n.tagName === 'form');
  const nome = achar(formGerar, n => n.placeholder === 'Nome');
  nome.value = '  davi ';
  selecoes[0].value = 'unlimited'; selecoes[0].listeners.change();
  const aviso = achar(formGerar, n => n.textContent === 'Ilimitado ainda respeita o teto global diário do servidor.');
  assert.equal(aviso.hidden, false, 'Aviso do teto global ao escolher Ilimitado');
  selecoes[0].value = 'daily'; selecoes[0].listeners.change();
  assert.equal(aviso.hidden, true);
  selecoes[0].value = 'unlimited'; selecoes[0].listeners.change();
  await formGerar.listeners.submit({preventDefault() {}});
  assert.deepEqual(chamadas.pop(), ['gerar', 'davi', 'unlimited', null, null]);
  assert.equal(achar(raiz, n => n.id === 'admin-codigo').textContent, 'ZT-CODIGO-FICTICIO');
  assert.match(texto(raiz), /só aparece agora/);
  assert.ok(botao('Copiar'));
  botao('Fechar').listeners.click();
  assert.equal(achar(raiz, n => n.id === 'admin-codigo'), null, 'Fechar apaga o código');
  assert.ok(!texto(raiz).includes('ZT-CODIGO-FICTICIO'));
  await ui.gerar('eva', 'daily', 5, null);
  assert.ok(achar(raiz, n => n.id === 'admin-codigo'));
  await ui.carregar();
  assert.equal(achar(raiz, n => n.id === 'admin-codigo'), null, 'Redesenhar apaga o código');

  // Alterar limite: "Zerar pacote" só no plano total.
  botao('Alterar limite', linhas[1]).listeners.click();
  let painel = achar(raiz, n => n.id === 'admin-painel');
  let zerar = achar(painel, n => n.tagName === 'label' && texto(n).includes('Zerar'));
  assert.equal(zerar.hidden, false);
  achar(painel, n => n.type === 'checkbox').checked = true;
  await botao('Salvar', painel).listeners.click();
  assert.deepEqual(chamadas.pop(), ['limite', 'bia', 'total', 100, null, true]);
  botao('Alterar limite', todos(raiz, n => n.tagName === 'tr')[1]).listeners.click();
  painel = achar(raiz, n => n.id === 'admin-painel');
  zerar = achar(painel, n => n.tagName === 'label' && texto(n).includes('Zerar'));
  assert.equal(zerar.hidden, true, 'Plano diário não tem Zerar pacote');

  // Validade no editor: vem preenchida com a atual; salvar mantém; campo limpo manda null (limpa a validade).
  tokens[2].expires = new Date(2030, 0, 15, 12).getTime();
  await ui.carregar();
  botao('Alterar limite', todos(raiz, n => n.tagName === 'tr')[3]).listeners.click();
  painel = achar(raiz, n => n.id === 'admin-painel');
  assert.equal(achar(painel, n => n.type === 'date').value, '2030-01-15');
  await botao('Salvar', painel).listeners.click();
  assert.deepEqual(chamadas.pop(), ['limite', 'caio', 'unlimited', null, new Date('2030-01-15T23:59:59').getTime(), false]);
  botao('Alterar limite', todos(raiz, n => n.tagName === 'tr')[3]).listeners.click();
  painel = achar(raiz, n => n.id === 'admin-painel');
  achar(painel, n => n.type === 'date').value = '';
  await botao('Salvar', painel).listeners.click();
  assert.deepEqual(chamadas.pop(), ['limite', 'caio', 'unlimited', null, null, false]);
  delete tokens[2].expires; await ui.carregar();

  // Revogar pede confirmação.
  chamadas.length = 0;
  const linha3 = todos(raiz, n => n.tagName === 'tr')[3];
  confirmou = false;
  await botao('Revogar', linha3).listeners.click();
  assert.equal(chamadas.length, 0, 'Sem confirmar, nada é revogado');
  confirmou = true;
  await botao('Revogar', linha3).listeners.click();
  assert.deepEqual(chamadas.pop(), ['revogar', 'caio']);
  // Falhas da ponte aparecem na tela; a senha digitada não é apagada se salvar falhou.
  const msg = () => achar(raiz, n => n.id === 'admin-msg').textContent;
  const api = window.pywebview.api, original = {...api};
  api.admin_ia_revogar = async () => { throw new Error('boom'); };
  await botao('Revogar', todos(raiz, n => n.tagName === 'tr')[3]).listeners.click();
  assert.equal(msg(), 'Não foi possível concluir. Tente novamente.');
  api.admin_ia_gerar = async () => { throw new Error('boom'); };
  assert.equal((await ui.gerar('x', 'unlimited', null, null)).erro, 'Não foi possível concluir. Tente novamente.');
  assert.equal(msg(), 'Não foi possível concluir. Tente novamente.');
  estado = {beta: true, senha: false}; await ui.carregar();
  const campo2 = achar(raiz, n => n.type === 'password');
  campo2.value = 'senha-ficticia';
  api.admin_ia_salvar_senha = async () => { throw new Error('boom'); };
  await achar(raiz, n => n.tagName === 'form').listeners.submit({preventDefault() {}});
  assert.equal(campo2.value, 'senha-ficticia', 'Falhou: o campo não é limpo');
  assert.equal(msg(), 'Não foi possível concluir. Tente novamente.');
  Object.assign(api, original);
  estado = {beta: true, senha: true}; await ui.carregar();

  // Cópia negada mostra "Copie à mão"; número vazio não chama a ponte.
  global.navigator = {clipboard: {writeText: () => Promise.reject(new Error('negado'))}};
  await ui.gerar('fim', 'unlimited', null, null);
  botao('Copiar').listeners.click();
  await flush();
  assert.equal(msg(), 'Copie à mão.');
  chamadas.length = 0;
  const form2 = achar(raiz, n => n.tagName === 'form');
  achar(form2, n => n.placeholder === 'Nome').value = 'zed';
  const sel = achar(form2, n => n.tagName === 'select'); sel.value = 'daily'; sel.listeners.change();
  await form2.listeners.submit({preventDefault() {}});
  assert.equal(msg(), 'Informe o número de usos.');
  assert.equal(chamadas.length, 0, 'Sem número, a ponte não é chamada');
  botao('Alterar limite', todos(raiz, n => n.tagName === 'tr')[2]).listeners.click();
  const painel2 = achar(raiz, n => n.id === 'admin-painel');
  achar(painel2, n => n.type === 'number').value = '';
  await botao('Salvar', painel2).listeners.click();
  assert.equal(msg(), 'Informe o número de usos.');
  assert.equal(chamadas.length, 0);
  console.log('admin_ia ui ok');
})().catch(e => { console.error(e); process.exit(1); });
