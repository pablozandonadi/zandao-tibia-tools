const assert = require('node:assert/strict');

class Element {
  constructor(tag = 'div') { this.tagName = tag; this.children = []; this.listeners = {}; this.dataset = {}; this.disabled = false; this.value = ''; this.textContent = ''; this.shown = false; this.classList = {contains: value => value === 'shown' && this.shown}; }
  set innerHTML(value) { throw new Error('Transcript must never use HTML'); }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  setAttribute(name, value) { this[name] = value; }
  append(...children) { children.forEach(child => { child.parent = this; this.children.push(child); }); }
  remove() { this.parent.children = this.parent.children.filter(child => child !== this); }
  querySelector(tag) { return this.children.find(child => child.tagName === tag); }
}
const ids = ['page-voz', 'voz-status', 'voz-esfera', 'voz-ouvi', 'voz-entendi', 'voz-resposta', 'voz-avisos', 'voz-microfone', 'voz-lista', 'voz-vazio', 'voz-quantidade', 'voz-feedback', 'voz-form', 'voz-valor', 'voz-unidade', 'voz-criar', 'voz-online-form', 'voz-online-token', 'voz-online-enabled', 'voz-online-status', 'voz-ajuda', 'voz-ajuda-texto', 'voz-ajuda-area'];
const elements = Object.fromEntries(ids.map(id => [id, new Element()]));
global.document = {getElementById: id => elements[id], createElement: tag => new Element(tag)};
const intervals = [];
global.setInterval = callback => intervals.push(callback);
global.window = {addEventListener() {}, toast: (texto, erro) => toasts.push([texto, erro])};
const ui = require('./web/voz.js');
let avisosApi = [{id: 'velho', texto: 'Antigo'}], toasts = [], sons = 0, timers = [], snapshots = 0, starts = 0, direct = false;
const calls = [];
const state = () => ({estado: 'ouvindo', detalhe: 'Ouvindo', microfone: true, ouvi: '<img src=x onerror=alert(1)>', resposta: 'Fala comigo, tibiano.', timers, online_enabled: true, online_configured: true, avisos: avisosApi});
window.pywebview = {api: {
  async voz_configurar_online(...args) { calls.push(['online', ...args]); return {...state(), online_enabled: args[1], online_configured: true}; },
  async voz_escutar() { calls.push(['listen']); direct = !direct; return {...state(), direto: direct}; },
  async voz_parar() { calls.push(['pause']); return {...state(), estado: 'pausado', microfone: false}; },
  async audio_tocar(...args) { sons++; assert.deepEqual(args, ['padrao:Potion.mp3', 100]); return true; },
  async voz_iniciar() { starts++; return state(); },
  async voz_estado() { snapshots++; return state(); },
  async voz_criar(...args) { calls.push(['create', ...args]); timers = [...timers, {id: 'id-1', label: '30 segundos', restante: 30, duracao: 30}]; return state(); },
  async voz_cancelar(...args) { calls.push(['cancel', ...args]); timers = timers.filter(timer => timer.id !== args[0]); return state(); }
}};
const flush = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  ui.boot();
  ui.boot();
  await flush();
  assert.equal(starts, 0, 'Voz pausada: o boot nunca liga microfone, Vosk ou Piper');
  assert.equal(snapshots, 1, 'O boot lê o estado uma única vez (sem iniciar a voz), para Configurações já nascer certa');
  assert.equal(elements['voz-online-enabled'].checked, true, 'Acesso online salvo e ligado aparece em Configurações sem abrir o Assistente');
  assert.equal(elements['voz-online-status'].textContent, 'IA do chat ativada.');
  ui.render({...state(),avisos:[{id:'timer-alert',texto:'Timer terminou.'}]});
  assert.equal(elements['voz-avisos'].textContent,'Timer terminou.');
  assert.equal(elements['voz-ouvi'].textContent, '<img src=x onerror=alert(1)>');
  assert.equal(elements['voz-entendi'].textContent, '—');
  ui.render({...state(), entendi:'Criar timer · 30 s'});
  assert.equal(elements['voz-entendi'].textContent, 'Criar timer · 30 s');
  assert.equal(typeof elements['voz-esfera'].listeners.click, 'function', 'Orb toggles microphone');
  await elements['voz-esfera'].listeners.click();
  assert.deepEqual(calls.shift(), ['listen']);
  assert.equal(elements['voz-esfera']['aria-label'], 'Desligar comandos diretos');
  assert.equal(elements['voz-esfera']['aria-pressed'], 'true');
  await elements['voz-esfera'].listeners.click();
  assert.deepEqual(calls.shift(), ['listen']);
  assert.equal(starts, 0);
  assert.equal(elements['voz-esfera']['aria-pressed'], 'false');
  assert.equal(elements['voz-esfera']['aria-label'], 'Ligar comandos diretos');
  elements['voz-ajuda-area'].listeners.mouseenter();
  assert.equal(elements['voz-ajuda'].listeners.mouseleave, undefined, 'Moving from button into tooltip must not dismiss it');
  assert.equal(elements['voz-ajuda-texto'].hidden, false);
  elements['voz-ajuda'].listeners.keydown({key: 'Escape'});
  assert.equal(elements['voz-ajuda-texto'].hidden, true);
  elements['voz-ajuda'].listeners.click();
  assert.equal(elements['voz-ajuda-texto'].hidden, false);
  elements['voz-ajuda'].listeners.blur();
  elements['voz-ajuda-area'].listeners.mouseleave();
  assert.equal(elements['voz-ajuda-texto'].hidden, false, 'Click pins help while pointer leaves');
  elements['voz-ajuda'].listeners.keydown({key: 'Escape'});
  assert.equal(elements['voz-ajuda-texto'].hidden, true);
  elements['voz-ajuda'].listeners.focus();
  elements['voz-ajuda-area'].listeners.mouseleave();
  assert.equal(elements['voz-ajuda-texto'].hidden, false, 'Keyboard focus retains help');
  elements['voz-ajuda'].listeners.blur();
  assert.equal(elements['voz-ajuda-texto'].hidden, true);
  ui.render({...state(), estado: 'erro'});
  assert.equal(elements['voz-esfera'].dataset.estado, 'erro');
  elements['voz-valor'].value = '30';
  elements['voz-unidade'].value = 'segundo';
  elements['voz-form'].listeners.submit({preventDefault() {}});
  await flush();
  assert.deepEqual(calls[0], ['create', 30, 'segundo']);
  assert.equal(elements['voz-lista'].children.length, 1);
  const cancel = elements['voz-lista'].children[0].querySelector('button');
  await ui.refresh();
  assert.equal(cancel.disabled, false, 'Polling must leave cancellation available');
  await cancel.listeners.click();
  assert.deepEqual(calls[1], ['cancel', 'id-1']);
  assert.equal(elements['voz-lista'].children.length, 0);
  assert.equal(ui.format(120), '2:00');
  assert.equal(ui.format(-1), '0:00');
  const previous = snapshots;
  intervals[0]();
  await flush();
  assert.equal(snapshots, previous, 'Aba oculta: o 1º segundo só faz a contagem regressiva');
  intervals[0]();
  await flush();
  assert.equal(snapshots, previous + 1, 'Aba oculta consulta os avisos a cada 2 s');
  elements['page-voz'].shown = true;
  intervals[0]();
  await flush();
  assert.equal(snapshots, previous + 2, 'Aba de voz consulta a cada 1 s');
  elements['page-voz'].shown = false;
  assert.deepEqual(toasts, [], 'Aviso que já existia no boot nunca reaparece');
  assert.equal(sons, 0);
  avisosApi = [...avisosApi, {id: 'a', texto: 'Timer de 30 s terminou.'}, {id: 'b', texto: '<b>Boss disponível</b>'}];
  await ui.refresh();
  await flush();
  assert.deepEqual(toasts, [['Timer de 30 s terminou.', undefined], ['<b>Boss disponível</b>', undefined]], 'Um toast (texto puro) por id novo');
  assert.equal(sons, 1, 'Um único som por consulta, mesmo com vários avisos');
  await ui.refresh();
  await flush();
  assert.equal(toasts.length, 2, 'Ids já vistos não repetem');
  assert.equal(sons, 1);
  const audioReal = window.pywebview.api.audio_tocar;
  delete window.pywebview.api.audio_tocar;
  delete window.AudioContext;
  avisosApi = [...avisosApi, {id: 'c', texto: 'Stamina cheia.'}];
  await ui.refresh();
  await flush();
  assert.equal(toasts.length, 3, 'Sem áudio disponível o toast aparece e nada lança');
  let bipes = 0, frequencia = 0;
  window.AudioContext = function () { this.destination = {}; this.currentTime = 0; this.createOscillator = () => ({frequency: {set value(v) { frequencia = v; }}, connect() {}, start() { bipes++; }, stop() {}}); };
  avisosApi = [...avisosApi, {id: 'd', texto: 'Mercado.'}];
  await ui.refresh();
  await flush();
  assert.deepEqual([bipes, frequencia], [1, 880], 'Sem o motor de timers cai no bipe de 880 Hz');
  delete window.AudioContext;
  window.pywebview.api.audio_tocar = audioReal;
  elements['voz-online-token'].value = 'a'.repeat(43);
  elements['voz-online-enabled'].checked = true;
  assert.equal(typeof elements['voz-online-form'].listeners.submit, 'function');
  elements['voz-online-form'].listeners.submit({preventDefault() {}});
  await flush();
  assert.equal(elements['voz-online-token'].value, '');
  assert.deepEqual(calls.at(-1), ['online', 'a'.repeat(43), true]);
  assert.equal(elements['voz-online-enabled'].checked, true);
  const html = require('node:fs').readFileSync(require('node:path').join(__dirname, 'web/index.html'), 'utf8');
  assert.equal((html.match(/id="voz-online-form"/g) || []).length, 1);
  assert.ok(html.indexOf('id="voz-online-form"') > html.indexOf('id="page-config"'));
  assert.equal(html.includes('<summary>Reconhecimento online</summary>'), false);
  for(const id of ['voz-form','voz-criar','voz-lista','voz-vazio','voz-quantidade'])delete elements[id];
  delete require.cache[require.resolve('./web/voz.js')];
  const noLegacy=require('./web/voz.js');noLegacy.boot();await flush();
  const before=toasts.length;avisosApi=[...avisosApi,{id:'new-without-form',texto:'Stamina sem formulário legado'}];
  elements['page-voz'].shown=false;await noLegacy.refresh();await flush();
  assert.equal(toasts.length,before+1,'Polling e avisos continuam sem o formulário legado e fora do Assistente');
  console.log('voz UI: paused boot (no auto-start), create, cancel, poll and safe transcript passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
