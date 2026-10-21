import { DatabaseSync } from 'node:sqlite';
import { existsSync, openSync, closeSync, mkdirSync, lstatSync, chmodSync } from 'node:fs';
import { dirname } from 'node:path';

// Only credentials, protocol keys and delivery metadata. No messages or QR table.
export class SessionStore {
 constructor(path) {
  if(path!==':memory:') {
   mkdirSync(dirname(path),{recursive:true,mode:0o700});
   if(existsSync(path)&&lstatSync(path).isSymbolicLink())throw Error('Invalid state path');
   if(!existsSync(path))closeSync(openSync(path,'wx',0o600));
   if(process.platform!=='win32')chmodSync(path,0o600);
  }
  this.db=new DatabaseSync(path);
  this.db.exec('PRAGMA busy_timeout=5000; PRAGMA synchronous=FULL; PRAGMA journal_mode=DELETE; CREATE TABLE IF NOT EXISTS kv(category TEXT NOT NULL,id TEXT NOT NULL,value TEXT NOT NULL,PRIMARY KEY(category,id)); CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY,state TEXT NOT NULL,receipt TEXT);');
  this.codec=JSON;
 }
 transaction(fn) {
  this.db.exec('BEGIN IMMEDIATE');
  try{const result=fn();this.db.exec('COMMIT');return result;}catch(error){this.db.exec('ROLLBACK');throw error;}
 }
 get(category,id) {
  const row=this.db.prepare('SELECT value FROM kv WHERE category=? AND id=?').get(category,id);
  return row?JSON.parse(row.value,this.codec.reviver):undefined;
 }
 put(category,id,value) {
  this.db.prepare('INSERT INTO kv(category,id,value) VALUES(?,?,?) ON CONFLICT(category,id) DO UPDATE SET value=excluded.value').run(category,id,JSON.stringify(value,this.codec.replacer));
 }
 revoked(){return this.get('meta','revoked')===true;}
 accept(now){this.transaction(()=>{if(this.revoked())throw Error('Revoked');this.put('meta','acceptedAt',now);});}
 accepted(){return typeof this.get('meta','acceptedAt')==='number';}
 revoke(){this.transaction(()=>{this.put('meta','revoked',true);this.db.exec("DELETE FROM kv WHERE category='creds' OR category LIKE 'signal:%'");});}
 auth(sdk) {
  this.codec=sdk.BufferJSON;
  if(this.revoked())throw Error('Revoked');
  let creds=this.get('creds','main');
  if(!creds){creds=sdk.initAuthCreds();this.transaction(()=>this.put('creds','main',creds));}
  const saveCreds=update=>{
   if(this.revoked())return;
   Object.assign(creds,update);
   this.transaction(()=>this.put('creds','main',creds));
  };
  const keys={
   get:async(type,ids)=>{
    const result=Object.create(null);if(this.revoked())return result;
    for(const id of ids){let value=this.get('signal:'+type,id);if(type==='app-state-sync-key'&&value)value=sdk.proto.Message.AppStateSyncKeyData.fromObject(value);if(value!==undefined)result[id]=value;}
    return result;
   },
   set:async(data)=>{
    this.transaction(()=>{
     if(this.revoked())throw Error('Revoked');
     for(const [type,values] of Object.entries(data))for(const [id,value] of Object.entries(values)){
      if(value===null||value===undefined)this.db.prepare('DELETE FROM kv WHERE category=? AND id=?').run('signal:'+type,id);
      else this.put('signal:'+type,id,value);
     }
    });
   },
   clear:async()=>{this.transaction(()=>this.db.exec("DELETE FROM kv WHERE category LIKE 'signal:%'"));}
  };
  return {state:{creds,keys},saveCreds};
 }
 beginAttempt(id) {
  return this.transaction(()=>{
   if(this.db.prepare('SELECT id FROM attempts WHERE id=?').get(id))return false;
   this.db.prepare("INSERT INTO attempts(id,state) VALUES(?,'sending')").run(id);return true;
  });
 }
 finishAttempt(id,state,receipt=null){this.transaction(()=>this.db.prepare('UPDATE attempts SET state=?,receipt=? WHERE id=?').run(state,receipt,id));}
 close(){this.db.close();}
}
