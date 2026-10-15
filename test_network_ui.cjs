/* Run with Playwright available in NODE_PATH; optional CHROME_PATH for installed Chrome. */
const {chromium}=require('playwright');
const fs=require('fs');
const path=require('path');
const {pathToFileURL}=require('url');
const assert=require('assert/strict');
(async()=>{
 const now=Date.now()/1000;
 const totals={since:now-14400,observed_seconds:14400,average:75,maximum:160,high_readings:7200,
  readings:14400,high_percent:50,high_seconds:7200,high_episodes:7,timeouts:12,failures:15,
  attempts:28800,failure_percent:.1,outages:2,disconnected_seconds:40,connected_seconds:14360,measurement_errors:0};
 const link=(id,name,connected)=>({id,name,alias:name,description:'Ethernet de teste',state:connected?'healthy':'offline',label:connected?'Conectado':'Desconectado',connected,connected_for:100,last_success:now,current:connected?40:null,average:50,maximum:160,p95:80,loss:0,jitter:5,selected:true,points:Array.from({length:300},(_,i)=>({t:now-300+i,ms:connected?40+i%12:null,loss:connected?0:100})),totals});
 const data={now,links:[link('fiber','Fibra',false),link('mobile','Celular',true)],events:[],selected:2,limit:8,config:{enabled:true,sound:true,notifications:true,excluded:[],aliases:{},preferred:''}};
 data.links[0].traffic={sent:1000000,received:1500000000,available:true,partial:false};
 data.links[1].traffic={sent:0,received:0,available:true,partial:false};
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 try{
 const page=await browser.newPage({viewport:{width:1250,height:1000}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('https://**/*',r=>r.abort());
 const index=path.resolve('web/index.html');
 await page.route('**/index.html',r=>{let html=fs.readFileSync(index,'utf8');html=html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,t=>t.includes('network.js')?t:'');return r.fulfill({contentType:'text/html',body:html});});
 await page.addInitScript(d=>{window.__netData=d;window.pywebview={api:{rede_estado:async()=>window.__netData,rede_configurar:async c=>{Object.assign(window.__netData.config,c);return window.__netData;}}};},data);
 await page.goto(pathToFileURL(index).href);
 await page.evaluate(()=>document.querySelectorAll('.page').forEach(p=>p.classList.toggle('shown',p.id==='page-rede')));
 await page.waitForFunction(()=>document.querySelectorAll('.net-link').length===2);
 assert.match(await page.locator('#net-summary').innerText(),/Uma conexão conectada/);
 assert.equal(await page.locator('#net-interval,#net-threshold').count(),0);
 assert.match(await page.locator('#net-session').innerText(),/7200 de 14400/);
 assert.match(await page.locator('#net-session').innerText(),/Enviado na sessão[\s\S]*1 MB/);
 assert.match(await page.locator('#net-session').innerText(),/1,5 GB/);
 assert.match(await page.locator('#net-session').innerText(),/0 B/);
 await page.evaluate(()=>delete window.__netData.links[1].traffic);
 await page.waitForFunction(()=>document.querySelector('#net-session').textContent.includes('Indisponível'));
 await page.evaluate(()=>window.__netData.links[1].traffic={sent:999,received:1000,available:false,partial:true});
 await page.waitForFunction(()=>document.querySelector('#net-session').textContent.includes('Totais parciais'));
 assert.match(await page.locator('#net-session').innerText(),/999 B[\s\S]*1 KB/);
 assert.doesNotMatch(await page.locator('#page-rede').innerText(),/Saudável|saudável/);
 const mobile=page.locator('[data-net-id="mobile"]');
 await mobile.locator('details').evaluate(e=>{e.open=true;});
 await mobile.locator('[data-net-preferred]').focus();
 await page.evaluate(()=>{const l=window.__netData.links[1];Object.assign(l,{state:'offline',label:'Desconectado',connected:false,current:null});});
 await page.waitForFunction(()=>document.querySelector('[data-net-id="mobile"] .net-state').textContent==='Desconectado');
 assert.match(await page.locator('#net-summary').innerText(),/Todas as conexões/);
 await mobile.locator('[data-net-alias]').fill('Nome em edição');
 await page.evaluate(()=>{const l=window.__netData.links[1];Object.assign(l,{state:'healthy',label:'Conectado',connected:true,current:40});});
 await page.waitForFunction(()=>document.querySelector('[data-net-id="mobile"] .net-state').textContent==='Conectado');
 assert.equal(await mobile.locator('[data-net-alias]').inputValue(),'Nome em edição');
 assert.equal(await mobile.locator('details').evaluate(e=>e.open),true);
 await page.setViewportSize({width:430,height:930});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 if(process.env.NETWORK_SCREENSHOT){await page.locator('#content').evaluate(e=>{e.scrollTop=600;});await page.screenshot({path:process.env.NETWORK_SCREENSHOT});}
 assert.deepEqual(errors,[]);
 console.log('Networking UI: focused controls stay live, edits survive, fixed cadence/threshold, full-session totals, narrow layout: OK');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
