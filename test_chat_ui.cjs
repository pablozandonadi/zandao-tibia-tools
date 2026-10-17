const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

class Element {
  constructor(tag = 'div') { this.tagName = tag; this.children = []; this.listeners = {}; this.className = ''; this.textContent = ''; this.value = ''; this.disabled = false; this.scrollTop = 0; this.scrollHeight = 500; this.focused = 0; }
  set innerHTML(value) { throw new Error('O chat nunca usa HTML'); }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  querySelector(selector) { return selector === 'button[type=submit]' ? this.submit : undefined; }
  focus() { this.focused++; }
}
const elements = Object.fromEntries(['chat-mensagens', 'chat-form', 'chat-texto', 'chat-limpar'].map(id => [id, new Element()]));
elements['chat-form'].submit = new Element('button');
global.document = {getElementById: id => elements[id], createElement: tag => new Element(tag)};
global.window = {addEventListener() {}};
const ui = require('./web/chat.js');

const calls = [];
let answer;
window.pywebview = {api: {
  assistente_chat(texto) { calls.push(['chat', texto]); return new Promise((resolve, reject) => { answer = {resolve, reject}; }); },
  async assistente_chat_limpar() { calls.push(['limpar']); return {ok: true}; }
}};
const flush = () => new Promise(resolve => setImmediate(resolve));
const caixa = elements['chat-mensagens'], form = elements['chat-form'], campo = elements['chat-texto'], enviar = form.submit;
const tag = (balao, nome) => balao.children.find(child => child.tagName === nome);
const submit = () => { let prevented = false; form.listeners.submit({preventDefault() { prevented = true; }}); return prevented; };

(async () => {
  // Balões: tudo entra por textContent, o "Entendi" só aparece quando houve ação.
  const html = '<img src=x onerror=alert(1)>';
  const bot = ui.render('chat-bot', html, '—');
  assert.equal(bot.className, 'chat-bot');
  assert.equal(tag(bot, 'p').textContent, html, 'HTML não é interpretado');
  assert.equal(tag(bot, 'small'), undefined, 'Sem ação, sem "Entendi"');
  assert.equal(tag(ui.render('chat-bot', 'ok', ''), 'small'), undefined);
  assert.equal(tag(ui.render('chat-bot', 'ok'), 'small'), undefined);
  const entendi = ui.render('chat-bot', 'Drume: 1 abate.', 'Registrar abate · <b>Drume</b>');
  assert.equal(tag(entendi, 'small').textContent, 'Entendi: Registrar abate · <b>Drume</b>');
  assert.equal(caixa.children.at(-1), entendi);
  assert.equal(caixa.scrollTop, caixa.scrollHeight, 'Rola para a última mensagem');
  caixa.replaceChildren();

  // Enter/botão: um envio por vez, botão desabilitado enquanto espera.
  ui.boot();
  assert.equal(submit(), true, 'O formulário nunca recarrega a página');
  campo.value = '   ';
  submit();
  assert.deepEqual(calls, [], 'Texto vazio não vai ao app');
  campo.value = '  matei o Drume ';
  submit();
  assert.deepEqual(calls, [['chat', 'matei o Drume']]);
  assert.equal(enviar.disabled, true, 'Botão desabilitado enquanto espera');
  assert.equal(campo.value, '', 'Campo limpo após enviar');
  assert.deepEqual(caixa.children.map(child => child.className), ['chat-eu']);
  assert.equal(tag(caixa.children[0], 'p').textContent, 'matei o Drume');
  campo.value = 'outra pergunta';
  submit();
  assert.equal(calls.length, 1, 'Segundo envio durante a espera é ignorado');
  answer.resolve({resposta: 'Drume: 1 abates reais.', entendi: 'Registrar abate · Drume', origem: 'local'});
  await flush();
  assert.deepEqual(caixa.children.map(child => child.className), ['chat-eu', 'chat-bot']);
  assert.equal(tag(caixa.children[1], 'p').textContent, 'Drume: 1 abates reais.');
  assert.equal(tag(caixa.children[1], 'small').textContent, 'Entendi: Registrar abate · Drume');
  assert.equal(enviar.disabled, false);
  assert.equal(campo.value, 'outra pergunta', 'O que foi digitado durante a espera é mantido');

  // Erros: do app ({erro}) e da própria ponte (promessa rejeitada).
  submit();
  answer.resolve({erro: 'Não consegui responder agora.'});
  await flush();
  const erro = caixa.children.at(-1);
  assert.ok(erro.className.split(' ').includes('chat-bot') && erro.className.split(' ').includes('chat-erro'));
  assert.equal(tag(erro, 'p').textContent, 'Não consegui responder agora.');
  assert.equal(enviar.disabled, false);
  campo.value = 'de novo';
  submit();
  answer.reject(new Error('A ponte caiu'));
  await flush();
  assert.equal(tag(caixa.children.at(-1), 'p').textContent, 'A ponte caiu');
  assert.equal(enviar.disabled, false, 'Erro também libera o botão');

  // Limpar zera a tela e o histórico do app.
  await elements['chat-limpar'].listeners.click();
  assert.deepEqual(calls.at(-1), ['limpar']);
  assert.equal(caixa.children.length, 0);

  // Tela: aba Chat, formulário, voz escondida mas presente, chat.js depois do assistente.js.
  const index = fs.readFileSync(path.join(__dirname, 'web/index.html'), 'utf8');
  const at = text => { const i = index.indexOf(text); assert.ok(i >= 0, text); return i; };
  assert.equal((index.match(/id="chat-form"/g) || []).length, 1);
  assert.ok(index.includes('data-assistente-tab="overview">Chat</button>'));
  assert.ok(at('id="chat-mensagens" role="log" aria-live="polite"') < at('id="chat-form"'));
  assert.ok(at('src="assistente.js"') < at('src="chat.js"'));
  const pausado = at('<div id="voz-pausado" hidden>');
  assert.ok(at('id="chat-form"') < at('id="voz-form"') && at('id="voz-lista"') < pausado, 'Chat no topo; timer manual e lista continuam visíveis');
  for (const id of ['voz-status', 'voz-microfone', 'voz-esfera', 'voz-ajuda', 'voz-ajuda-texto', 'voz-ajuda-area', 'voz-ouvi', 'voz-entendi', 'voz-resposta']) assert.ok(at(`id="${id}"`) > pausado, `${id} fica escondido no #voz-pausado`);
  for (const id of ['voz-form', 'voz-valor', 'voz-unidade', 'voz-criar', 'voz-feedback', 'voz-quantidade', 'voz-vazio', 'voz-lista']) assert.ok(at(`id="${id}"`) < pausado, `${id} continua visível`);
  console.log('chat UI: safe bubbles, single send, errors, clear and page wiring passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
