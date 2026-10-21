/* Synthetic browser origin and Google/API fixtures; all network intercepted. */
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 try{
  const page=await browser.newPage(),errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));
  let logged=false,connected=false,revoked=false,subscriptions=[],config={},mode='simulation',holdCheck=false,releaseCheck,groupLabel='Grupo <script>malicioso</script>',previewText='Prévia <img src=x onerror=alert(1)>';
  await page.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),path=url.pathname;requests.push({path,auth:req.headers().authorization});
   if(url.hostname==='accounts.google.com')return route.fulfill({contentType:'application/javascript',body:`window.google={accounts:{id:{initialize:c=>{window.googleNonce=c.nonce;window.googleCallback=c.callback},renderButton:e=>{e.textContent='Google sintético'}}}};`});
   if(path==='/portal')return route.fulfill({contentType:'text/html; charset=utf-8',body:fs.readFileSync('portal/index.html','utf8')});
   if(path==='/portal.js')return route.fulfill({contentType:'application/javascript',body:fs.readFileSync('portal/portal.js','utf8')});
   if(path==='/public-config')return route.fulfill({json:{clientId:'synthetic-client',mode}});
   if(path==='/auth/check'){
    assert.equal(req.postDataJSON().nonce,await page.evaluate(()=>googleNonce));
    if(holdCheck)await new Promise(resolve=>releaseCheck=resolve);
    return route.fulfill({status:req.headers().authorization==='Bearer synthetic-id-token'?200:401,json:{ok:req.headers().authorization==='Bearer synthetic-id-token'}});
   }
   if(!path.startsWith('/v1/'))throw Error('Unexpected request '+path);
   assert.equal(req.headers().authorization,'Bearer synthetic-id-token');assert.equal(url.search,'');logged=true;
   let result={};const body=req.postDataJSON();
   if(path==='/v1/subscriptions'&&req.method()==='GET')result=subscriptions;
   else if(path==='/v1/connections'&&req.method()==='GET')result=connected||revoked?[{id:'connection',state:revoked?'revoked':'active'}]:[];
   else if(path==='/v1/connections'&&req.method()==='POST'){assert.equal(body.riskAccepted,true);connected=true;revoked=false;result={id:'connection'};}
   else if(path==='/v1/connections/connection/pair')result={state:'pairing'};
   else if(path==='/v1/connections/connection'&&req.method()==='GET')result={state:'connected',simulated:true};
   else if(path==='/v1/connections/connection/groups')result=[{id:'opaque-group',label:groupLabel}];
   else if(path==='/v1/connections/connection'&&req.method()==='DELETE'){revoked=true;connected=false;result={state:'revoked'};}
   else if(path==='/v1/preview'){config=body;result={text:previewText,reference_date:'2026-10-21'};}
   else if(path==='/v1/destinations'){assert.equal(body.group,'opaque-group');result={id:'destination'};}
   else if(path.startsWith('/v1/subscriptions')&&['POST','PUT'].includes(req.method())){subscriptions=[{id:'subscription',...body,state:body.active?'active':'inactive'}];result=subscriptions[0];}
   else if(path==='/v1/runs')result=[{state:'simulated'}];
   else throw Error('Unknown API request '+path);
   return route.fulfill({json:result});
  });
  await page.goto('https://portal.test/portal');await page.waitForFunction(()=>window.googleCallback);
  assert.equal(await page.locator('#settings').isVisible(),false);
  await page.evaluate(()=>googleCallback({credential:'wrong-nonce-token'}));assert.equal(await page.locator('#settings').isVisible(),false);assert.match(await page.locator('#notice').textContent(),/Não foi possível verificar/);
  await page.evaluate(()=>googleCallback({credential:'synthetic-id-token'}));await page.locator('#settings').waitFor();assert.equal(logged,true);
  await page.locator('#import').setInputFiles({name:'config.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({personagem:'Pirata Teste',mundo:'Antica',blocks:{mundo:true},timezone:'UTC',generateAt:'12:00',sendAt:'12:10'}))});
  await page.locator('#preview').click();assert.match(await page.locator('#preview-result').textContent(),/<img/);assert.equal(await page.locator('#preview-result img').count(),0);assert.equal(config.personagem,'Pirata Teste');
  await page.locator('#pair').click();assert.match(await page.locator('#notice').textContent(),/Aceite os riscos/);assert.equal(connected,false);
  await page.locator('#risk').check();await page.locator('#pair').click();await page.locator('#groups').selectOption('opaque-group');assert.equal(await page.locator('#groups script').count(),0);
  await page.locator('#save').click();await page.waitForFunction(text=>document.getElementById('notice').textContent.includes(text),'simulação salva e pausada');assert.match(await page.locator('#notice').textContent(),/simulação salva e pausada/);await page.locator('#activate').click();await page.waitForFunction(text=>document.getElementById('notice').textContent.includes(text),'Nenhuma mensagem real');assert.match(await page.locator('#notice').textContent(),/Nenhuma mensagem real/);
  await page.locator('#pause').click();await page.waitForFunction(text=>document.getElementById('notice').textContent.includes(text),'Agenda pausada');assert.match(await page.locator('#notice').textContent(),/pausada/);await page.locator('#runs').click();await page.waitForFunction(()=>document.getElementById('runs-result').textContent.includes('Simulado'));assert.match(await page.locator('#runs-result').textContent(),/Simulado/);
  groupLabel='Piratas do Rocks';previewText='Prévia de simulação · Mundo: Antica';await page.locator('#refresh').click();await page.locator('#groups').selectOption('opaque-group');await page.locator('#preview').click();await page.waitForFunction(()=>document.getElementById('preview-result').textContent.includes('Prévia de simulação'));
  if(process.env.MA_SCREENSHOT_DIR){await page.setViewportSize({width:1200,height:1000});await page.screenshot({path:process.env.MA_SCREENSHOT_DIR+'/portal-mensagem-automatica.png',fullPage:true});}
  await page.locator('#revoke').click();await page.waitForFunction(text=>document.getElementById('notice').textContent.includes(text),'revogada');assert.match(await page.locator('#notice').textContent(),/revogada/);assert.equal(revoked,true);
  assert.equal(await page.evaluate(()=>localStorage.length),0);assert.equal(await page.evaluate(()=>sessionStorage.length),0);
  assert.ok(requests.every(r=>!r.path.includes('synthetic-id-token')));await page.locator('#logout').click();assert.equal(await page.locator('#settings').isVisible(),false);assert.match(await page.locator('#config-summary').textContent(),/Nenhuma configuração/);
  holdCheck=true;const checked=page.waitForResponse(r=>new URL(r.url()).pathname==='/auth/check');await page.evaluate(()=>{window.pendingCallback=googleCallback({credential:'synthetic-id-token'});});while(!releaseCheck)await new Promise(resolve=>setTimeout(resolve,1));
  await page.evaluate(()=>window.dispatchEvent(new Event('pagehide')));releaseCheck();await checked;await page.evaluate(()=>pendingCallback);assert.equal(await page.locator('#settings').isVisible(),false,'Late callback cannot log in after logout');
  await page.setViewportSize({width:320,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);
  console.log('Portal Google sintético: memória/bearer, importar/prévia, aceite, conexão/grupo opaco, salvar/ativar simulação/pausar/revogar, logout e 320px passaram.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
