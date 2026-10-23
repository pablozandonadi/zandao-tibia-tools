const assert = require('node:assert/strict');

// DOM mínimo (como em test_admin_mensagens_ui.cjs): sem HTML interpretado, sem storage.
class Classes { constructor() { this.set = new Set(); } toggle(n, on) { on ? this.set.add(n) : this.set.delete(n); } contains(n) { return this.set.has(n); } }
class Element {
  constructor(tag = 'div') { this.tagName = tag; this.children = []; this.listeners = {}; this.className = ''; this.textContent = ''; this.value = ''; this.checked = false; this.hidden = false; this.classList = new Classes(); this.dataset = {}; }
  set innerHTML(value) { throw new Error('A página Admin nunca usa HTML'); }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
}
const raiz = new Element(), outros = {ia: new Element(), msg: new Element()}, barra = new Element();
const abas = ['ia', 'msg', 'cmd'].map(n => { const a = new Element('span'); a.dataset.adminAba = n; return a; });
barra.querySelectorAll = () => abas;
const achar = (no, teste) => { if (typeof no === 'string') return null; if (teste(no)) return no; for (const c of no.children) { const r = achar(c, teste); if (r) return r; } return null; };
const todos = (no, teste, acc = []) => { if (typeof no === 'string') return acc; if (teste(no)) acc.push(no); no.children.forEach(c => todos(c, teste, acc)); return acc; };
const texto = no => typeof no === 'string' ? no : no.textContent + no.children.map(texto).join('');
const porId = {'admin-cmd-raiz': raiz, 'admin-raiz': outros.ia, 'admin-msg-raiz': outros.msg, 'admin-abas': barra};
global.document = { createElement: tag => new Element(tag), getElementById: id => porId[id] || null };
global.localStorage = {setItem() { throw new Error('nada de storage'); }};
global.sessionStorage = global.localStorage;
let lista = {}, chamadas = [], falha = null;
global.window = {addEventListener() {}, pywebview: {api: {
  async admin_cmd_listar() { return lista; },
  async admin_cmd_salvar(...a) { chamadas.push(['salvar', ...a]); return falha || {ok: true}; },
  async admin_cmd_restaurar(...a) { chamadas.push(['restaurar', ...a]); return {ok: true}; }
}}};
const ui = require('./web/admin_comandos.js');
const flush = () => new Promise(r => setImmediate(r));
const botao = (no, rotulo) => achar(no, n => n.tagName === 'button' && n.textContent === rotulo);

(async () => {
  await flush();
  // Abas: só o painel escolhido fica visível.
  ui.abrirAba('cmd');
  assert.equal(raiz.hidden, false); assert.equal(outros.ia.hidden, true); assert.equal(outros.msg.hidden, true);
  assert.deepEqual(abas.map(a => a.classList.contains('on')), [false, false, true]);
  abas[0].listeners.click(); assert.equal(outros.ia.hidden, false); assert.equal(raiz.hidden, true);
  ui.abrirAba('nada'); assert.equal(outros.ia.hidden, false, 'aba desconhecida é ignorada');

  // Erro do servidor: só a mensagem.
  lista = {erro: 'Somente o administrador pode fazer isso.'};
  await ui.carregar();
  assert.ok(texto(raiz).includes('Somente o administrador')); assert.equal(achar(raiz, n => n.tagName === 'textarea'), null);

  // Lista dos dois bots; nomes e textos nunca viram HTML.
  const ataque = '<img src=x onerror=alert(1)>';
  lista = {bots: {
    whatsapp: [{cmd: 'help', label: '!help', enabled: true, text: '', default: 'LISTA PADRAO', example: '', vars: [{name: 'resposta', desc: 'a resposta padrão inteira'}]},
               {cmd: 'duelo', label: ataque, enabled: false, text: ataque, default: '', example: 'Ana x Bia', vars: [{name: 'nome1', desc: 'primeiro personagem'}, {name: 'resposta', desc: 'tudo'}]}],
    assistente: [{cmd: 'exp', label: 'exp', enabled: true, text: '', default: '', example: 'Rasteibra', vars: [{name: 'titulo', desc: 'primeira linha'}]}]}};
  await ui.carregar();
  const cartoes = todos(raiz, n => n.className === 'card');
  assert.equal(cartoes.length, 3);
  assert.ok(texto(raiz).includes('Bot do WhatsApp') && texto(raiz).includes('Bot do assistente tibiano'));
  assert.equal(achar(cartoes[1], n => n.tagName === 'h3').textContent, ataque);
  const [caixaHelp, caixaDuelo] = cartoes.map(c => achar(c, n => n.type === 'checkbox'));
  assert.equal(caixaHelp.checked, true); assert.equal(caixaDuelo.checked, false);
  assert.equal(achar(cartoes[1], n => n.tagName === 'textarea').value, ataque);

  // Salvar envia o bot, o comando, o estado e o texto; "padrão como base" só existe quando há padrão.
  const textoHelp = achar(cartoes[0], n => n.tagName === 'textarea');
  assert.equal(botao(cartoes[1], 'Usar o texto padrão como base'), null);
  botao(cartoes[0], 'Usar o texto padrão como base').listeners.click(); assert.equal(textoHelp.value, 'LISTA PADRAO');
  textoHelp.value = 'Oi!\n{resposta}'; caixaHelp.checked = false;
  await botao(cartoes[0], 'Salvar').listeners.click();
  assert.deepEqual(chamadas.pop(), ['salvar', 'whatsapp', 'help', false, 'Oi!\n{resposta}']);
  assert.ok(texto(cartoes[0]).includes('Salvo.'));
  await botao(cartoes[2], 'Salvar').listeners.click(); assert.deepEqual(chamadas.pop(), ['salvar', 'assistente', 'exp', true, '']);

  // Variáveis: cada uma é um botão que insere {nome} no texto; a prévia manda o texto ainda não salvo e o exemplo.
  const textoDuelo = achar(cartoes[1], n => n.tagName === 'textarea');
  const chip = botao(cartoes[1], '{nome1}'); assert.equal(chip.title, 'primeiro personagem');
  textoDuelo.value = 'Duelo: '; chip.listeners.click(); assert.equal(textoDuelo.value, 'Duelo: {nome1}');
  assert.equal(botao(cartoes[0], '{resposta}') !== null, true);
  const exemploDuelo = achar(cartoes[1], n => n.placeholder === 'Exemplo para a prévia'); assert.equal(exemploDuelo.value, 'Ana x Bia');
  global.window.pywebview.api.admin_cmd_previa = async (...a) => { chamadas.push(['previa', ...a]); return {texto: 'Duelo: Ana'}; };
  await botao(cartoes[1], 'Prévia').listeners.click();
  assert.deepEqual(chamadas.pop(), ['previa', 'whatsapp', 'duelo', 'Duelo: {nome1}', 'Ana x Bia']);
  assert.equal(achar(cartoes[1], n => n.tagName === 'pre').textContent, 'Duelo: Ana');
  global.window.pywebview.api.admin_cmd_previa = async () => ({erro: 'Este exemplo não é um uso válido do comando.'});
  await botao(cartoes[1], 'Prévia').listeners.click(); assert.ok(texto(cartoes[1]).includes('não é um uso válido'));
  chamadas.length = 0;

  // Erro ao salvar aparece no cartão; restaurar limpa o cartão.
  falha = {erro: 'Texto de até 1500 caracteres.'};
  await botao(cartoes[0], 'Salvar').listeners.click(); assert.ok(texto(cartoes[0]).includes('Texto de até 1500')); chamadas.length = 0; falha = null;
  await botao(cartoes[0], 'Restaurar padrão').listeners.click();
  assert.deepEqual(chamadas.pop(), ['restaurar', 'whatsapp', 'help']); assert.equal(textoHelp.value, ''); assert.equal(caixaHelp.checked, true);
  console.log('admin comandos ui ok');
})().catch(e => { console.error(e); process.exit(1); });
