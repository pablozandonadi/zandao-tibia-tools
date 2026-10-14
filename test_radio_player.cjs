const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('web/radio.js', 'utf8').split('(function () {')[0];
const context = {globalThis: {}, Promise, Date}; vm.createContext(context);
vm.runInContext(source + '\nglobalThis.Player = BrasilHitsPlayer;', context);
const Player = context.globalThis.Player;
function setup() {
  let next = 1; const pending = new Map(), audios = [];
  const timers = {setTimeout(fn) {const id = next++; pending.set(id, fn); return id;}, clearTimeout(id) {pending.delete(id);}};
  const factory = () => {
    const events = {};
    const audio = {currentTime:0, paused:false, addEventListener(e,fn) {events[e]=fn;}, play() {return Promise.resolve();}, pause() {this.paused=true;}, removeAttribute() {this.src='';}, load() {}, fire(e) {events[e]();}};
    audios.push(audio); return audio;
  };
  return {player:new Player({audioFactory:factory,timers}),pending,audios};
}
{
  const {player,audios,pending} = setup();
  player.play('one'); assert.equal(player.state,'conectando');
  audios[0].fire('playing'); assert.equal(player.state,'tocando');
  audios[0].fire('error'); assert.equal(player.state,'reconectando');
  const retry = [...pending.values()][0];
  player.stop(); retry(); assert.equal(audios.length,1); assert.equal(player.state,'parado'); assert.equal(pending.size,0);
}
{
  const {player,audios} = setup();
  player.play('one'); player.play('two');
  audios[0].fire('playing'); audios[0].fire('error');
  assert.equal(player.state,'conectando'); assert.equal(audios[0].paused,true); assert.equal(audios[0].src,'');
  audios[1].fire('playing'); player.setVolume(.2); assert.equal(audios[1].volume,.2);
  assert.equal(player.state,'tocando');
}
{
  const {player,audios,pending} = setup(); player.play('one');
  for (let i=0;i<5;i++) {audios.at(-1).fire('error'); if (i<4) {const retry=[...pending.values()][0];pending.clear();retry();}}
  assert.equal(player.state,'indisponível'); assert.equal(player.wanted,false); assert.equal(audios.length,5);
}
console.log('Rádio: parada cancela reconexão; eventos antigos ignorados; volume e limite de tentativas OK.');
