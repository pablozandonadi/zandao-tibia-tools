import { createServer } from 'node:http';
import { timingSafeEqual } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { BaileysBridge, BridgeFailure, INTERNAL_ID } from './adapter.mjs';

const reply=(response,status,body)=>{response.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'});response.end(JSON.stringify(body));};
async function body(request,allowed){
 let size=0;const chunks=[];
 for await(const chunk of request){size+=chunk.length;if(size>65536)throw new BridgeFailure();chunks.push(chunk);}
 const value=JSON.parse(Buffer.concat(chunks).toString());
 if(!value||Array.isArray(value)||typeof value!=='object'||Object.keys(value).some(key=>!allowed.includes(key)))throw new BridgeFailure();
 return value;
}
export function handler(bridge){return async(request,response)=>{
 const expected=Buffer.from('Bearer '+bridge.token),actual=Buffer.from(request.headers.authorization||'');
 if(actual.length!==expected.length||!timingSafeEqual(actual,expected)){reply(response,401,{error:'unauthorized'});return;}
 if(request.headers.origin||Number(request.headers['content-length']||0)>65536){reply(response,403,{error:'forbidden'});return;}
 const parts=request.url.split('/').filter(Boolean);
 if(parts.length<2||parts.length>3||parts[0]!=='sessions'||!INTERNAL_ID.test(parts[1])){reply(response,404,{error:'not found'});return;}
 try{
  const id=parts[1];let result;
  if(parts.length===2&&request.method==='GET')result=bridge.status(id);
  else if(parts.length===2&&request.method==='DELETE')result=await bridge.revoke(id);
  else if(parts[2]==='pair'&&request.method==='POST')result=await bridge.pair(id,(await body(request,['riskAccepted'])).riskAccepted);
  else if(parts[2]==='resume'&&request.method==='POST')result=await bridge.resume(id);
  else if(parts[2]==='groups'&&request.method==='GET')result={groups:await bridge.groups(id)};
  else if(parts[2]==='send'&&request.method==='POST')result=await bridge.send(id,await body(request,['group','text','attempt']));
  else{reply(response,404,{error:'not found'});return;}
  reply(response,200,result);
 }catch(error){const dispatch=error instanceof BridgeFailure?error.dispatch:'not_started';reply(response,dispatch==='uncertain'?502:409,{error:'unavailable',dispatch});}
};}
export async function start(env=process.env){
 const token=readFileSync(env.BRIDGE_TOKEN_FILE,'utf8').trim();
 const bridge=new BaileysBridge({token,dir:env.BRIDGE_STATE_DIR,mode:env.BRIDGE_MODE||'fake',enableReal:env.BRIDGE_ENABLE_REAL||''});
 const server=createServer(handler(bridge));server.requestTimeout=15000;server.headersTimeout=5000;server.keepAliveTimeout=30000;server.maxHeadersCount=40;
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(8788,'127.0.0.1',resolve);});
 console.info('bridge ready on loopback');
 return {server,bridge};
}
if(process.argv[1]&&fileURLToPath(import.meta.url)===resolve(process.argv[1])){
 start().then(({server,bridge})=>{
  const stop=()=>{server.close();server.closeIdleConnections();void bridge.close().finally(()=>process.exit(0));};process.once('SIGTERM',stop);process.once('SIGINT',stop);
 }).catch(()=>{console.error('bridge configuration or startup unavailable');process.exitCode=1;});
}
