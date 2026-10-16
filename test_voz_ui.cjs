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
const ids = ['page-voz', 'voz-status', 'voz-esfera', 'voz-ouvi', 'voz-resposta', 'voz-microfone', 'voz-lista', 'voz-vazio', 'voz-quantidade', 'voz-feedback', 'voz-form', 'voz-valor', 'voz-unidade', 'voz-criar', 'voz-online-form', 'voz-online-token', 'voz-online-enabled', 'voz-online-status'];
const elements = Object.fromEntries(ids.map(id => [id, new Element()]));
global.document = {getElementById: id => elements[id], createElement: tag => new Element(tag)};
const intervals = [];
global.setInterval = callback => intervals.push(callback);
global.window = {addEventListener() {}};
const ui = require('./web/voz.js');
let timers = [], snapshots = 0, starts = 0;
const calls = [];
const state = () => ({estado: 'ouvindo', detalhe: 'Ouvindo', microfone: true, ouvi: '<img src=x onerror=alert(1)>', resposta: 'Fala comigo, tibiano.', timers});
window.pywebview = {api: {
  async voz_configurar_online(...args) { calls.push(['online', ...args]); return {...state(), online_enabled: args[1], online_configured: true}; },
  async voz_escutar() { calls.push(['listen']); return {...state(), estado: 'escutando'}; },
  async voz_parar() { calls.push(['pause']); return {...state(), estado: 'pausado', microfone: false}; },
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
  assert.equal(starts, 1, 'Start automatically, only once');
  assert.equal(elements['voz-ouvi'].textContent, '<img src=x onerror=alert(1)>');
  assert.equal(typeof elements['voz-esfera'].listeners.click, 'function', 'Orb starts a command');
  await elements['voz-esfera'].listeners.click();
  assert.deepEqual(calls.shift(), ['listen']);
  assert.equal(elements['voz-esfera'].dataset.estado, 'escutando');
  assert.equal(elements['voz-esfera']['aria-label'], 'Falar um comando');
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
  assert.equal(snapshots, previous, 'Hidden page does not poll');
  elements['page-voz'].shown = true;
  intervals[0]();
  await flush();
  assert.equal(snapshots, previous + 1);
  elements['voz-online-token'].value = 'a'.repeat(43);
  elements['voz-online-enabled'].checked = true;
  assert.equal(typeof elements['voz-online-form'].listeners.submit, 'function');
  elements['voz-online-form'].listeners.submit({preventDefault() {}});
  await flush();
  assert.equal(elements['voz-online-token'].value, '');
  assert.deepEqual(calls.at(-1), ['online', 'a'.repeat(43), true]);
  assert.equal(elements['voz-online-enabled'].checked, true);
  console.log('voz UI: auto-start, create, cancel, poll and safe transcript passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
