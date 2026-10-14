const assert = require('node:assert/strict');
const {escape, color, clamp, normalize} = require('./web/mirror.js');
assert.equal(escape('<img src=x onerror="alert(1)">'), '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
assert.equal(escape("O'Neil & >"), 'O&#39;Neil &amp; &gt;');
assert.equal(color('#ABC123'), '#ABC123');
assert.equal(color('red; background:url(x)'), '#ff6b3d');
assert.equal(clamp('bad', .25, 8, 1), 1);
assert.equal(clamp(-3, .25, 8, 1), .25);
assert.equal(clamp(99, 0, 1, 1), 1);
assert.deepEqual(normalize({}), {personagem:'',perfis:[],ativo:'',perfil:null,estado:{},clientes:[]});
assert.equal(normalize({personagem:'Knight',perfis:null,clientes:{}}).personagem,'Knight');
assert.deepEqual(normalize({clientes:{}}).clientes,[]);
console.log('Mirror UI: escaping, safe color, numeric boundaries and empty state passed.');

// Exercise rendering and request generations with a deliberately delayed bridge.
const vm = require('node:vm');
const fs = require('node:fs');
(async () => {
  const host = {innerHTML:'', contains:()=>true};
  const listeners = {};
  const replies = [];
  const window = {
    document: {getElementById:()=>host, addEventListener:(name,fn)=>{listeners[name]=fn;}},
    addEventListener:(name,fn)=>{listeners[name]=fn;},
    pywebview:{api:{mirror_carregar:()=>new Promise(resolve=>replies.push(resolve))}}
  };
  const context = vm.createContext({window, document:window.document});
  vm.runInContext(fs.readFileSync(require.resolve('./web/mirror.js'),'utf8'),context);
  const first = window.mirrorLoad();
  const second = window.mirrorLoad();
  replies[1]({personagem:'Atual',perfis:[],clientes:[]}); await second;
  replies[0]({personagem:'Antigo',perfis:[],clientes:[]}); await first;
  assert.match(host.innerHTML,/Atual/);
  assert.doesNotMatch(host.innerHTML,/Antigo/);
  listeners.mirrorEstado({detail:{personagem:'Antigo',perfis:[],estado:{erro:'Resposta obsoleta'}}});
  assert.doesNotMatch(host.innerHTML,/Resposta obsoleta/);
  listeners.mirrorEstado({detail:{personagem:'Atual',perfis:[],estado:{mensagem:'<script>bad()</script>'}}});
  assert.match(host.innerHTML,/&lt;script&gt;bad\(\)&lt;\/script&gt;/);
  assert.doesNotMatch(host.innerHTML,/<script>/);
    // Reload retains an active selection, including Portuguese pendente responses.
  const activeLoad = window.mirrorLoad();
  replies[2]({personagem:'Atual',perfis:[],estado:{estado:'aguardando_foco'}}); await activeLoad;
  assert.match(host.innerHTML,/data-action="cancelar-selecao" >/);
  assert.match(host.innerHTML,/data-action="reload" disabled/);
  window.pywebview.api.mirror_cancelar = async()=>({ok:true,cancelado:true});
  const cancelTarget = {dataset:{action:'cancelar-selecao'}, disabled:false, closest:()=>null};
  listeners.click({target:{closest:()=>cancelTarget}});
  await new Promise(resolve=>setImmediate(resolve));
  assert.doesNotMatch(host.innerHTML,/data-action="cancelar-selecao"/);
  listeners.mirrorEstado({detail:{personagem:'Atual',perfis:[],pendente:true,estado:{estado:'sem_cliente'}}});
  assert.match(host.innerHTML,/data-action="cancelar-selecao" >/);
  listeners.mirrorEstado({detail:{personagem:'Antigo',perfis:[],cancelado:true}});
  assert.match(host.innerHTML,/data-action="cancelar-selecao" >/);
  listeners.mirrorEstado({detail:{personagem:'Atual',perfis:[],cancelado:true,estado:{estado:'sem_cliente'}}});
  assert.doesNotMatch(host.innerHTML,/data-action="cancelar-selecao"/);
  window.pywebview = null; await window.mirrorLoad();
  assert.match(host.innerHTML,/Prévia da interface/);
  assert.match(host.innerHTML,/data-action="quadrado" disabled/);
  console.log('Mirror UI: stale loads/events, native message escaping and preview controls passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});

