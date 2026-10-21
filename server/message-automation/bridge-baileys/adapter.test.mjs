import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,rmSync,writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {EventEmitter} from 'node:events';
import {createServer} from 'node:http';
import {SessionStore} from './store.mjs';
import {BaileysBridge,encryptedMount} from './adapter.mjs';
import {handler} from './main.mjs';
const sdk=await import('@whiskeysockets/baileys'); // No real socket is constructed.
const token='synthetic-test-token-'.repeat(3),id='a'.repeat(32),other='b'.repeat(32),attempt='c'.repeat(32);
function fixture(t,extra={}){
 const dir=mkdtempSync(join(tmpdir(),'zt-baileys-test-')),sockets=[],configs=[];
 const mock={...sdk,default:config=>{configs.push(config);const s={ev:new EventEmitter(),ended:0,loggedOut:0,sends:0,end(){this.ended++;},async logout(){this.loggedOut++;},async groupFetchAllParticipating(){return {'123@g.us':{subject:'Sintético'},'123@s.whatsapp.net':{subject:'Contato'}};},async sendMessage(jid,text,opts){this.sends++;return {key:{id:opts.messageId}};}};sockets.push(s);return s;}};
 const bridge=new BaileysBridge({mode:'real',token,dir,enableReal:'I_ACCEPT_UNOFFICIAL_WHATSAPP'},{verifyMount(){},loadSDK:async()=>mock,qrImage:async()=> 'data:image/png;base64,synthetic',...extra});
 t.after(async()=>{await bridge.close();rmSync(dir,{recursive:true,force:true});});return {bridge,dir,sockets,configs};
}
async function connected(f,key=id){await f.bridge.pair(key,true);f.sockets.at(-1).ev.emit('connection.update',{connection:'open'});}
test('SQLite preserves BufferJSON protocol keys, transactions, attempts and durable revocation',async t=>{
 const dir=mkdtempSync(join(tmpdir(),'zt-store-test-')),path=join(dir,'session.sqlite');let store=new SessionStore(path);t.after(()=>{store.close();rmSync(dir,{recursive:true,force:true});});
 let auth=store.auth(sdk);auth.saveCreds({registered:true});store.accept(1);await auth.state.keys.set({session:{x:{key:Buffer.from([1,2])}},'app-state-sync-key':{a:{keyData:Buffer.from([4])}}});assert.equal(store.beginAttempt(attempt),true);
 store.close();store=new SessionStore(path);auth=store.auth(sdk);assert.equal(auth.state.creds.registered,true);assert.equal(store.accepted(),true);assert.deepEqual((await auth.state.keys.get('session',['x'])).x.key,Buffer.from([1,2]));assert.deepEqual(Buffer.from((await auth.state.keys.get('app-state-sync-key',['a'])).a.keyData),Buffer.from([4]));assert.equal(store.beginAttempt(attempt),false);
 assert.throws(()=>store.transaction(()=>{store.put('test','rollback',true);throw Error();}));assert.equal(store.get('test','rollback'),undefined);
 await auth.state.keys.set({session:{x:null}});assert.equal((await auth.state.keys.get('session',['x'])).x,undefined);await auth.state.keys.clear();assert.equal((await auth.state.keys.get('app-state-sync-key',['a'])).a,undefined);
 store.revoke();auth.saveCreds({registered:true});assert.equal(store.get('creds','main'),undefined);await assert.rejects(auth.state.keys.set({session:{x:{}}}));assert.throws(()=>store.auth(sdk));
});
test('fake is offline, explicitly simulated, and duplicate attempts never retry',async t=>{
 const b=new BaileysBridge({token},{loadSDK:()=>{throw Error('must stay offline');}});t.after(()=>b.close());await assert.rejects(b.pair(id,false));assert.equal((await b.pair(id,true)).simulated,true);assert.equal((await b.groups(id))[0].id,'fake-group');assert.deepEqual(await b.send(id,{group:'fake-group',text:'synthetic',attempt}),{id:attempt,simulated:true});await assert.rejects(b.send(id,{group:'fake-group',text:'synthetic',attempt}),e=>e.dispatch==='uncertain');await b.revoke(id);await assert.rejects(b.pair(id,true));await assert.rejects(b.resume(id));
});
test('socket blocks all history and content retention; opaque groups are session isolated',async t=>{
 const f=fixture(t);await connected(f);await connected(f,other);for(const [i,c] of f.configs.entries()){assert.equal(c.syncFullHistory,false);assert.equal(c.shouldSyncHistoryMessage({syncType:0}),false);assert.equal(c.shouldSyncHistoryMessage({syncType:2}),false);assert.equal(c.markOnlineOnConnect,false);assert.equal(c.enableRecentMessageCache,false);assert.equal(await c.getMessage({}),undefined);assert.deepEqual(f.sockets[i].ev.eventNames().sort(),['connection.update','creds.update']);}
 const a=await f.bridge.groups(id),b=await f.bridge.groups(other);assert.equal(a.length,1);assert.notEqual(a[0].id,b[0].id);assert.equal(a[0].id.includes('@'),false);await assert.rejects(f.bridge.send(other,{group:a[0].id,text:'x',attempt}),e=>e.dispatch==='not_started');assert.deepEqual(await f.bridge.send(id,{group:a[0].id,text:'x',attempt}),{id:attempt,simulated:false});assert.equal(f.sockets[0].sends,1);
});
test('QR expires and delayed QR never replaces open connection',async t=>{
 let now=100000,resolveQR;const f=fixture(t,{clock:()=>now,qrImage:()=>new Promise(resolve=>resolveQR=resolve)});await f.bridge.pair(id,true);f.sockets[0].ev.emit('connection.update',{qr:'synthetic'});resolveQR('data:image/png;base64,synthetic');await Promise.resolve();assert.equal(f.bridge.status(id).state,'pairing');now+=31000;assert.equal(f.bridge.status(id).qrImage,undefined);f.sockets[0].ev.emit('connection.update',{qr:'other'});f.sockets[0].ev.emit('connection.update',{connection:'open'});resolveQR('data:image/png;base64,synthetic');await Promise.resolve();assert.equal(f.bridge.status(id).state,'connected');assert.equal(f.bridge.status(id).qrImage,undefined);
});
test('revoke closes socket even if SQLite fails and remains fail-stop',async t=>{
 const f=fixture(t);await connected(f);const store=f.bridge.session(id).store,original=store.revoke.bind(store);store.revoke=()=>{throw Error('disk failure');};await assert.rejects(f.bridge.revoke(id));assert.equal(f.sockets[0].ended,1);assert.equal(f.sockets[0].loggedOut,1);assert.equal(f.bridge.status(id).state,'revoked');await assert.rejects(f.bridge.pair(id,true));await assert.rejects(f.bridge.resume(id));await assert.rejects(f.bridge.groups(id));store.revoke=original;original();
});
test('post-dispatch failure stays uncertain without another socket send',async t=>{
 const f=fixture(t);await connected(f);const group=(await f.bridge.groups(id))[0].id;f.sockets[0].sendMessage=async()=>{f.sockets[0].sends++;throw Error('network after dispatch');};for(let i=0;i<2;i++)await assert.rejects(f.bridge.send(id,{group,text:'x',attempt}),e=>e.dispatch==='uncertain');assert.equal(f.sockets[0].sends,1);assert.equal(f.bridge.session(id).store.db.prepare('SELECT state FROM attempts WHERE id=?').get(attempt).state,'uncertain');
});
test('startup does not reconnect; resume requires consent and registered credentials',async t=>{
 const f=fixture(t),s=f.bridge.session(id);assert.equal(f.sockets.length,0);await assert.rejects(f.bridge.resume(id));s.store.auth(sdk).saveCreds({registered:true});s.store.accept(1);const result=f.bridge.resume(id);await new Promise(resolve=>setImmediate(resolve));f.sockets[0].ev.emit('connection.update',{connection:'open'});assert.equal((await result).state,'connected');await f.bridge.revoke(id);const fresh=new BaileysBridge({mode:'real',token,dir:f.dir,enableReal:'I_ACCEPT_UNOFFICIAL_WHATSAPP'},{verifyMount(){},loadSDK:()=>{throw Error('no startup reconnect');}});try{assert.equal(fresh.status(id).state,'revoked');await assert.rejects(fresh.resume(id));}finally{await fresh.close();}
});
test('real gates refuse ordinary mounts, absent admin consent and legacy directories',t=>{
 assert.throws(()=>encryptedMount('/state',{},'win32'));const io={realpathSync:v=>v==='/state'?'/state':'/dev/dm-0',readFileSync:p=>p==='/proc/self/mountinfo'?'1 0 0:1 / /state rw - ext4 /dev/mapper/state rw':'CRYPT-LUKS2-fixture'};encryptedMount('/state',io,'linux');assert.throws(()=>encryptedMount('/state',{...io,readFileSync:p=>p==='/proc/self/mountinfo'?io.readFileSync(p):'LVM-fixture'},'linux'));assert.throws(()=>new BaileysBridge({mode:'real',token}));const dir=mkdtempSync(join(tmpdir(),'zt-legacy-test-'));t.after(()=>rmSync(dir,{recursive:true,force:true}));writeFileSync(join(dir,'legacy-auth'),'not read');assert.throws(()=>new BaileysBridge({mode:'real',token,dir,enableReal:'I_ACCEPT_UNOFFICIAL_WHATSAPP'},{verifyMount(){}}));
});
test('private HTTP rejects bad auth, browser origins, unknown fields and large bodies',async t=>{
 const b=new BaileysBridge({token}),server=createServer(handler(b));await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));t.after(async()=>{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));await b.close();});const base='http://127.0.0.1:'+server.address().port+'/sessions/'+id,headers={Authorization:'Bearer '+token,'Content-Type':'application/json'};assert.equal((await fetch(base)).status,401);assert.equal((await fetch(base,{headers:{...headers,Origin:'https://invalid.example'}})).status,403);assert.equal((await fetch(base+'/pair',{method:'POST',headers,body:JSON.stringify({riskAccepted:true,owner:'forged'})})).status,409);assert.equal((await fetch(base+'/pair',{method:'POST',headers,body:JSON.stringify({riskAccepted:true})})).status,200);assert.equal((await (await fetch(base+'/send',{method:'POST',headers,body:JSON.stringify({group:'fake-group',text:'synthetic',attempt})})).json()).simulated,true);assert.equal((await fetch(base+'/send',{method:'POST',headers,body:'x'.repeat(65537)})).status,403);
});
