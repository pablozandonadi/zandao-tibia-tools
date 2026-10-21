import { createHmac } from 'node:crypto';
import { readFileSync, realpathSync, existsSync, readdirSync, writeFileSync } from 'node:fs';
import { basename, join, sep } from 'node:path';
import { SessionStore } from './store.mjs';

export const INTERNAL_ID=/^[a-f0-9]{32}$/;
export class BridgeFailure extends Error {
 constructor(dispatch='not_started'){super('Bridge unavailable');this.dispatch=dispatch;}
}
const silent={level:'silent',trace(){},debug(){},info(){},warn(){},error(){},fatal(){},child(){return this;}};
const within=async(promise,ms=8000)=>{
 let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new BridgeFailure('uncertain')),ms);})]);}finally{clearTimeout(timer);}
};
export function encryptedMount(dir,io={readFileSync,realpathSync},platform=process.platform) {
 if(platform!=='linux')throw new BridgeFailure();
 const absolute=io.realpathSync(dir);let best='',source='';
 const decode=value=>value.replace(/\\([0-7]{3})/g,(_,octal)=>String.fromCharCode(parseInt(octal,8)));
 for(const line of io.readFileSync('/proc/self/mountinfo','utf8').split('\n')){
  const [left,right]=line.split(' - ');if(!right)continue;const mount=decode(left.split(' ')[4]||'');
  if(mount&&(absolute===mount||absolute.startsWith(mount===sep?sep:mount+sep))&&mount.length>best.length){best=mount;source=right.split(' ')[1];}
 }
 const device=io.realpathSync(source),name=basename(device);
 if(!/^dm-\d+$/.test(name)||!io.readFileSync('/sys/class/block/'+name+'/dm/uuid','utf8').startsWith('CRYPT-LUKS'))throw new BridgeFailure();
}

export class BaileysBridge {
 constructor({mode='fake',token,dir='',enableReal=''},deps={}) {
  if(!['fake','real'].includes(mode)||typeof token!=='string'||token.length<32)throw new BridgeFailure();
  this.real=mode==='real';this.token=token;this.dir=dir;this.sessions=new Map();this.clock=deps.clock||(()=>Date.now());
  this.loadSDK=deps.loadSDK||(()=>import('@whiskeysockets/baileys'));
  this.qrImage=deps.qrImage||(async code=>{const QR=await import('qrcode');return QR.toDataURL(code,{width:300});});
  if(this.real){
   if(enableReal!=='I_ACCEPT_UNOFFICIAL_WHATSAPP')throw new BridgeFailure();
   (deps.verifyMount||encryptedMount)(dir);
   const marker=join(dir,'.baileys-bridge-v1');
   if(!existsSync(marker)){
    // Never import/guess ownership of a legacy auth directory, even on an encrypted mount.
    if(readdirSync(dir).length)throw new BridgeFailure();
    writeFileSync(marker,'isolated-session-store-v1\n',{flag:'wx',mode:0o600});
   }else if(readFileSync(marker,'utf8')!=='isolated-session-store-v1\n')throw new BridgeFailure();
  }
 }
 session(id) {
  if(!INTERNAL_ID.test(id))throw new BridgeFailure();
  if(this.sessions.has(id))return this.sessions.get(id);
  if(this.sessions.size>=50)throw new BridgeFailure();
  const store=new SessionStore(this.real?join(this.dir,id+'.sqlite'):':memory:');
  const s={id,store,state:store.revoked()?'revoked':this.real?'disconnected':'connected',socket:null,qr:'',expires:0,epoch:0,qrEpoch:0,tail:Promise.resolve(),persistenceFailed:false};
  this.sessions.set(id,s);return s;
 }
 async locked(id,fn){const s=this.session(id),run=s.tail.then(()=>fn(s));s.tail=run.catch(()=>{});return run;}
 status(id){
  const s=this.session(id);const blocked=s.state==='revoked'||s.persistenceFailed;const result={state:blocked?'revoked':s.store.revoked()?'revoked':s.state,simulated:!this.real};
  if(!blocked&&s.qr&&s.expires>this.clock()/1000&&!s.store.revoked()){result.qrImage=s.qr;result.expiresAt=s.expires;result.state='pairing';}else{s.qr='';s.expires=0;}
  return result;
 }
 async connect(s,pairing) {
  if(s.state==='revoked'||s.persistenceFailed||s.store.revoked())throw new BridgeFailure();
  if(s.state==='connected')return;
  if(s.socket&&s.qr&&s.expires>this.clock()/1000)return;
  const sdk=await this.loadSDK();const auth=s.store.auth(sdk);
  if(!pairing&&(!s.store.accepted()||auth.state.creds.registered!==true))throw new BridgeFailure();
  if(s.socket){s.epoch++;await within(Promise.resolve(s.socket.end(undefined))).catch(()=>{});}
  const epoch=++s.epoch;s.qr='';s.expires=0;s.persistenceFailed=false;s.state='disconnected';s.ready=new Promise(resolve=>s.readyResolve=resolve);
  const socket=sdk.default({auth:auth.state,logger:silent,markOnlineOnConnect:false,syncFullHistory:false,
   shouldSyncHistoryMessage:()=>false,
   enableRecentMessageCache:false,getMessage:async()=>undefined,connectTimeoutMs:8000,defaultQueryTimeoutMs:8000});
  s.socket=socket;
  socket.ev.on('creds.update',update=>{
   if(epoch!==s.epoch||s.persistenceFailed||s.state==='revoked'||s.store.revoked())return;
   try{auth.saveCreds(update);}catch{ s.persistenceFailed=true;s.state='disconnected';void Promise.resolve(socket.end(undefined)).catch(()=>{}); }
  });
  socket.ev.on('connection.update',update=>{
   if(epoch!==s.epoch||s.persistenceFailed||s.state==='revoked'||s.store.revoked())return;
   if(update.qr){const code=update.qr,qrEpoch=++s.qrEpoch,expires=Math.floor(this.clock()/1000)+30;void this.qrImage(code).then(image=>{if(epoch===s.epoch&&qrEpoch===s.qrEpoch&&s.state!=='connected'&&!s.store.revoked()){s.qr=image;s.expires=expires;s.state='pairing';}}).catch(()=>{});}
   if(update.connection==='open'){s.qrEpoch++;s.state='connected';s.qr='';s.expires=0;s.readyResolve(true);}
   if(update.connection==='close'){
    s.qrEpoch++;s.state='disconnected';s.qr='';s.expires=0;s.readyResolve(false);
    if(update.lastDisconnect?.error?.output?.statusCode===sdk.DisconnectReason.loggedOut){s.state='revoked';try{s.store.revoke();}catch{s.persistenceFailed=true;}}
   }
  });
  // No messages.upsert, messaging-history.set, receipt handler, readMessages or message store.
 }
 async pair(id,riskAccepted){return this.locked(id,async s=>{
  if(riskAccepted!==true||s.state==='revoked'||s.persistenceFailed||s.store.revoked())throw new BridgeFailure();
  s.store.accept(this.clock());if(this.real)await this.connect(s,true);return this.status(id);
 });}
 async resume(id){return this.locked(id,async s=>{
  if(s.state==='revoked'||s.persistenceFailed||s.store.revoked()||!s.store.accepted()||(this.real&&s.store.get('creds','main')?.registered!==true))throw new BridgeFailure();
  if(this.real){await this.connect(s,false);if(s.state!=='connected'&&!await within(s.ready))throw new BridgeFailure();}return this.status(id);
 });}
 handle(id,jid){return createHmac('sha256',this.token).update(id+'\0'+jid).digest('hex');}
 async groupMap(s){
  if(s.state!=='connected'||s.persistenceFailed||s.store.revoked())throw new BridgeFailure();
  if(!this.real)return new Map([['fake-group',{id:'fake-group',label:'Grupo sintético (simulação)',jid:''}]]);
  const groups=await within(s.socket.groupFetchAllParticipating());const result=new Map();
  for(const [jid,value] of Object.entries(groups||{}))if(jid.endsWith('@g.us')){const id=this.handle(s.id,jid);result.set(id,{id,label:typeof value.subject==='string'?value.subject:'Grupo',jid});}
  return result;
 }
 async groups(id){return this.locked(id,async s=>[...(await this.groupMap(s)).values()].map(({id,label})=>({id,label})));}
 async revoke(id){return this.locked(id,async s=>{
  s.state='revoked';s.epoch++;s.qrEpoch++;s.qr='';s.expires=0;
  let pending=false,persistenceError=false;
  try{s.store.revoke();}catch{s.persistenceFailed=true;persistenceError=true;}finally{
   if(s.socket){try{await within(Promise.resolve().then(()=>s.socket.logout()));}catch{pending=true;}finally{await within(Promise.resolve().then(()=>s.socket.end(undefined))).catch(()=>{});s.socket=null;}}
  }
  if(persistenceError)throw new BridgeFailure();
  return {state:'revoked',simulated:!this.real,...(pending?{remoteLogoutPending:true}:{})};
 });}
 async send(id,{group,text,attempt}){return this.locked(id,async s=>{
  if(typeof group!=='string'||typeof text!=='string'||!text||Buffer.byteLength(text)>64000||[...text].length>16000||!INTERNAL_ID.test(attempt))throw new BridgeFailure();
  const target=(await this.groupMap(s)).get(group);if(!target)throw new BridgeFailure();
  if(!s.store.beginAttempt(attempt))throw new BridgeFailure('uncertain');
  if(!this.real){s.store.finishAttempt(attempt,'simulated',attempt);return {id:attempt,simulated:true};}
  try{
   const message=await within(s.socket.sendMessage(target.jid,{text},{messageId:attempt}));
   const receipt=message?.key?.id;
   if(s.persistenceFailed||typeof receipt!=='string'||!/^[A-Za-z0-9._-]{1,128}$/.test(receipt))throw new BridgeFailure('uncertain');
   s.store.finishAttempt(attempt,'accepted',receipt);return {id:receipt,simulated:false};
  }catch{try{s.store.finishAttempt(attempt,'uncertain');}catch{}throw new BridgeFailure('uncertain');}
 });}
 async close(){for(const s of this.sessions.values()){s.epoch++;if(s.socket)await within(Promise.resolve(s.socket.end(undefined))).catch(()=>{});s.store.close();}this.sessions.clear();}
}
