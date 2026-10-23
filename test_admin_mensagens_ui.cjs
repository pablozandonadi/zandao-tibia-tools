const assert = require('node:assert/strict');

// DOM mínimo (como em test_admin_ia_ui.cjs): sem HTML interpretado, sem storage.
class Element {
  constructor(tag = 'div') { this.tagName = tag; this.children = []; this.listeners = {}; this.className = ''; this.textContent = ''; this.value = ''; }
  set innerHTML(value) { throw new Error('A página Admin nunca usa HTML'); }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
}
const raiz = new Element();
const achar = (no, teste) => { if (typeof no === 'string') return null; if (teste(no)) return no; for (const c of no.children) { const r = achar(c, teste); if (r) return r; } return null; };
const todos = (no, teste, acc = []) => { if (typeof no === 'string') return acc; if (teste(no)) acc.push(no); no.children.forEach(c => todos(c, teste, acc)); return acc; };
const texto = no => typeof no === 'string' ? no : no.textContent + no.children.map(texto).join('');
global.document = { createElement: tag => new Element(tag), getElementById: id => id === 'admin-msg-raiz' ? raiz : achar(raiz, n => n.id === id) };
let lista = {codigos: [], contas: []}, chamadas = [], confirmou = true, copiado = null;
global.confirm = () => confirmou;
Object.defineProperty(global, 'navigator', {configurable: true, value: {clipboard: {writeText: async t => { copiado = t; }}}}); // no Node novo `navigator` é só leitura
global.localStorage = {setItem() { throw new Error('nada de storage'); }};
global.sessionStorage = global.localStorage;
global.window = {addEventListener() {}, pywebview: {api: {
  async admin_msg_listar() { return lista; },
  async admin_msg_gerar(...a) { chamadas.push(['gerar', ...a]); return a[0] === 'recusado' ? {erro: 'Usos de 1 a 1000.'} : {codigo: 'CODIGO-FICTICIO'}; },
  async admin_msg_revogar(id) { chamadas.push(['revogar', id]); return {ok: true}; },
  async admin_msg_remover_conta(o) { chamadas.push(['remover', o]); return {ok: true}; }
}}};
const ui = require('./web/admin_mensagens.js');
const flush = () => new Promise(r => setImmediate(r));
const botao = rotulo => achar(raiz, n => n.tagName === 'button' && n.textContent === rotulo);

(async () => {
  await flush();
  // Erro do servidor (conta que não é administradora): só a mensagem, sem formulário.
  lista = {erro: 'Somente o administrador pode fazer isso.'};
  await ui.carregar();
  assert.ok(texto(raiz).includes('Somente o administrador'));
  assert.equal(achar(raiz, n => n.tagName === 'form'), null);

  // Lista: nome do cliente nunca vira HTML; conta de administrador não tem "Remover acesso".
  const ataque = '<img src=x onerror=alert(1)>';
  lista = {
    codigos: [{id: 'a'.repeat(16), note: ataque, uses: 1, created: 100}, {id: 'b'.repeat(16), note: 'Bia', uses: 0, created: 100}],
    contas: [{owner: 'c'.repeat(32), note: 'dono', since: 100, admin: true}, {owner: 'd'.repeat(32), note: 'Bia', since: 100, admin: false}]
  };
  await ui.carregar();
  const linhas = todos(raiz, n => n.tagName === 'tr');
  assert.equal(linhas.length, 2 + 2 + 2, '2 cabeçalhos + 2 códigos + 2 contas');
  assert.equal(linhas[1].children[0].textContent, ataque);
  assert.deepEqual([linhas[1].children[1].textContent, linhas[2].children[1].textContent], ['1 restante', '0 restantes']);
  assert.equal(todos(raiz, n => n.tagName === 'button' && n.textContent === 'Remover acesso').length, 1);

  // Gerar: valida antes de chamar; o código aparece uma vez e some ao fechar.
  const form = achar(raiz, n => n.tagName === 'form');
  const nome = achar(form, n => n.placeholder === 'Nome do cliente'), usos = achar(form, n => n.type === 'number');
  nome.value = '  '; await form.listeners.submit({preventDefault() {}});
  assert.ok(texto(raiz).includes('Informe o nome do cliente.')); assert.equal(chamadas.length, 0);
  nome.value = 'Davi'; usos.value = '0'; await form.listeners.submit({preventDefault() {}});
  assert.ok(texto(raiz).includes('Usos de 1 a 1000.')); assert.equal(chamadas.length, 0);
  usos.value = '2'; await form.listeners.submit({preventDefault() {}});
  assert.deepEqual(chamadas.pop(), ['gerar', 'Davi', 2]);
  assert.equal(achar(raiz, n => n.id === 'admin-msg-codigo').textContent, 'CODIGO-FICTICIO');
  await botao('Copiar').listeners.click(); assert.equal(copiado, 'CODIGO-FICTICIO');
  botao('Fechar').listeners.click();
  assert.equal(achar(raiz, n => n.id === 'admin-msg-codigo'), null, 'o código some ao fechar');
  await ui.carregar();
  assert.ok(!texto(raiz).includes('CODIGO-FICTICIO'), 'o código não volta ao redesenhar');

  // Erro do servidor ao gerar aparece na tela e não mostra código.
  const form2 = achar(raiz, n => n.tagName === 'form');
  achar(form2, n => n.placeholder === 'Nome do cliente').value = 'recusado';
  achar(form2, n => n.type === 'number').value = '1';
  await form2.listeners.submit({preventDefault() {}});
  assert.ok(texto(raiz).includes('Usos de 1 a 1000.')); assert.equal(achar(raiz, n => n.id === 'admin-msg-codigo'), null);
  chamadas.length = 0;

  // Revogar / remover: pedem confirmação e usam o id certo.
  confirmou = false; await botao('Revogar').listeners.click(); assert.equal(chamadas.length, 0, 'sem confirmação, nada acontece');
  confirmou = true;
  await botao('Revogar').listeners.click(); assert.deepEqual(chamadas.pop(), ['revogar', 'a'.repeat(16)]);
  await botao('Remover acesso').listeners.click(); assert.deepEqual(chamadas.pop(), ['remover', 'd'.repeat(32)]);
  console.log('admin mensagens ui ok');
})().catch(e => { console.error(e); process.exit(1); });
