/* Trusted local interface with native-bridge fixtures; no Google, bearer or WhatsApp. */
const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),assert=require('assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 try{
  const page=await browser.newPage(),errors=[],requests=[],calls=[];page.on('pageerror',e=>errors.push(e.message));
  const folder=path.resolve(__dirname,'../../web/mensagem_automatica_portal');let connected=false,revoked=false,subscriptions=[],watchesList=[],groupLabel='Grupo <script>malicioso</script>',previewText='Prévia <img src=x onerror=alert(1)>',releasePreview,signalPreview;
  const previewStarted=new Promise(r=>signalPreview=r),previewGate=new Promise(r=>releasePreview=r);let first=true;
  const configuration={personagem:'Pirata Teste',mundo:'Antica',blocks:{mundo:true},timezone:'UTC',generateAt:'12:00',sendAt:'12:10'};
  await page.exposeBinding('nativeCall',async(_,action,args=[])=>{
   calls.push({action,args});if(action==='boot')return {mode:'simulation',config:configuration};
   if(action==='reveal_recovery')return {code:'f'.repeat(64)};
   if(action==='recover'){assert.equal(args[0],'f'.repeat(64));return {ok:true};}
   assert.equal(action,'request');const [p,method,body]=args;let result={};
   if(p==='/v1/subscriptions'&&method==='GET')result=subscriptions;
   else if(p==='/v1/connections'&&method==='GET')result=connected||revoked?[{id:'connection',state:revoked?'revoked':'active'}]:[];
   else if(p==='/v1/connections'&&method==='POST'){assert.equal(body.riskAccepted,true);connected=true;revoked=false;result={id:'connection'};}
   else if(p==='/v1/connections/connection/pair')result={state:'pairing'};
   else if(p==='/v1/connections/connection'&&method==='GET')result={state:'connected',simulated:true};
   else if(p==='/v1/connections/connection/groups')result=[{id:'opaque-group',label:groupLabel}];
   else if(p==='/v1/connections/connection'&&method==='DELETE'){revoked=true;connected=false;result={state:'revoked'};}
   else if(p==='/v1/preview'){assert.equal(body.personagem,'Pirata Teste');if(first){first=false;signalPreview();await previewGate;}result={text:previewText,reference_date:'2026-10-21'};}
   else if(p==='/v1/destinations'){assert.equal(body.group,'opaque-group');result={id:'destination'};}
   else if(p.startsWith('/v1/subscriptions')&&['POST','PUT'].includes(method)){subscriptions=[{id:'subscription',...body,destinationLabel:groupLabel,state:body.active?'active':'inactive'}];result=subscriptions[0];}
   else if(p==='/v1/subscriptions/subscription'&&method==='DELETE'){subscriptions=[];result={id:'subscription',state:'revoked'};}
   else if(p==='/v1/watches'&&method==='GET')result=watchesList;
   else if(p==='/v1/watches'&&method==='POST'){watchesList=[{id:'watch',...body,destinationLabel:groupLabel,state:'active'}];result=watchesList[0];}
   else if(p==='/v1/watches/watch'&&method==='PUT'){watchesList=[{...watchesList[0],...body,state:body.active?'active':'inactive'}];result=watchesList[0];}
   else if(p==='/v1/watches/watch'&&method==='DELETE'){watchesList=[];result={id:'watch',state:'revoked'};}
   else if(p==='/v1/runs')result=[{subscription:'subscription',state:'simulated',reference:'2026-10-21'}];
   else throw Error('Unexpected native operation '+p);
   return {data:result};
  });
  await page.addInitScript(()=>{window.pywebview={api:Object.fromEntries(['boot','request','reveal_recovery','recover'].map(name=>[name,(...args)=>window.nativeCall(name,args)]))};});
  await page.route('**/*',async route=>{const url=new URL(route.request().url());requests.push(url.pathname);assert.equal(url.hostname,'local.test');assert.ok(['/index.html','/portal.js','/portal.css'].includes(url.pathname));return route.fulfill({contentType:url.pathname.endsWith('.js')?'application/javascript':url.pathname.endsWith('.css')?'text/css':'text/html; charset=utf-8',body:fs.readFileSync(path.join(folder,url.pathname.slice(1)))});});
  await page.goto('https://local.test/index.html');await page.locator('#settings').waitFor();
  await page.locator('#new-routine').click();await page.waitForFunction(()=>document.getElementById('ed-personagem').value==='Pirata Teste');
  assert.equal(await page.locator('#ed-blocks input').count(),13);assert.equal(await page.locator('#ed-fields input[data-value]').count(),9);assert.equal(await page.locator('#ed-extras input[data-arg]').count(),7);
  assert.equal(await page.locator('[data-group="blocks"][data-key="mundo"]').isChecked(),true);assert.equal(await page.locator('#ed-generate').inputValue(),'12:00');
  assert.equal(await page.locator('#recovery-code').textContent(),'');assert.equal(calls.some(c=>c.action==='reveal_recovery'),false);
  await page.locator('#preview').click();await previewStarted;assert.equal(await page.locator('#preview-result').textContent(),'');releasePreview();await page.waitForFunction(()=>document.getElementById('preview-result').textContent.includes('<img'));assert.equal(await page.locator('#preview-result img').count(),0);
  await page.locator('#pair').click();await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('Aceite os riscos'));assert.equal(connected,false);
  await page.locator('#risk').check();await page.locator('#pair').click();await page.waitForFunction(()=>document.getElementById('groups').options.length>1);
  await page.locator('#group-search').fill('nada assim');assert.equal(await page.locator('#groups option').count(),1);await page.locator('#group-search').fill('MALICIOSO');
  await page.locator('#groups').selectOption('opaque-group');assert.equal(await page.locator('#groups script').count(),0);
  await page.locator('#save').click();await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('salva e pausada'));assert.equal(await page.locator('#editor').isVisible(),false);
  const routine=page.locator('#routines article');await routine.getByRole('button',{name:'Editar'}).click();await page.waitForFunction(()=>document.getElementById('groups').value==='opaque-group');
  await page.locator('#ed-send').fill('12:20');await page.locator('#activate').click();await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('Nenhuma mensagem real'));
  await routine.getByText('Ativa',{exact:true}).waitFor();assert.equal(await page.locator('#routines script').count(),0);assert.ok((await routine.textContent()).includes('Gera 12:00 · Envia 12:20'));
  await routine.getByRole('button',{name:'Pausar'}).click();await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('Rotina pausada'));
  await routine.getByRole('button',{name:'Histórico'}).click();await page.waitForFunction(()=>document.getElementById('runs-result').textContent.includes('Simulado'));
  await page.locator('#runs').click();await page.waitForFunction(()=>document.getElementById('runs-title').textContent==='Todo o histórico');
  await routine.getByRole('button',{name:'Excluir'}).click();assert.equal(subscriptions.length,1);await routine.getByRole('button',{name:'Confirmar exclusão'}).click();await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('Rotina excluída'));assert.equal(subscriptions.length,0);
  // Alertas da guild: criar (com nome hostil), pausar e excluir; o texto do servidor nunca vira HTML.
  await page.locator('#watch-groups').selectOption('opaque-group');await page.locator('#watch-guild').fill('<img src=x onerror=alert(1)>Piratas');
  for(const [milestone,cap,expected,minute] of [['0','20','de 1 a 1000','3'],['50','1001','de 0 a 1000','3'],['50','20','por minuto','0']]){
   await page.locator('#watch-milestone').fill(milestone);await page.locator('#watch-cap').fill(cap);await page.locator('#watch-minute').fill(minute);await page.locator('#watch-save').click();
   await page.waitForFunction(text=>document.getElementById('notice').textContent.includes(text),expected);assert.equal(watchesList.length,0);
  }
  await page.locator('#watch-cap').fill('20');await page.locator('#watch-minute').fill('3');await page.locator('#watch-milestone').fill('100');await page.locator('#watch-save').click();
  await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('Alerta de simulação ativado'));
  const watch=page.locator('#watches article');assert.equal(await page.locator('#watches img').count(),0);assert.ok((await watch.textContent()).includes('Level ups a cada 100'));
  assert.equal(watchesList[0].milestone,100);assert.equal(watchesList[0].deaths,true);assert.equal(watchesList[0].hourlyCap,20);assert.equal(watchesList[0].perMinute,3);assert.equal(watchesList[0].active,true);
  await watch.getByRole('button',{name:'Pausar'}).click();await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('Alerta pausado'));assert.equal(watchesList[0].state,'inactive');
  await watch.getByRole('button',{name:'Excluir'}).click();assert.equal(watchesList.length,1);await watch.getByRole('button',{name:'Confirmar exclusão'}).click();
  await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('Alerta excluído'));assert.equal(watchesList.length,0);
  await page.locator('#access-controls summary').click();await page.locator('#reveal-recovery').click();await page.waitForFunction(()=>document.getElementById('recovery-code').textContent.length===64);await page.locator('#recovery-input').fill('f'.repeat(64));await page.locator('#recover').click();await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('Acesso recuperado'));assert.equal(await page.locator('#recovery-code').textContent(),'');assert.equal(await page.locator('#recovery-input').inputValue(),'');
  groupLabel='Piratas do Rocks';previewText='Prévia de simulação · Mundo: Antica';await page.locator('#refresh').click();await page.locator('#new-routine').click();await page.waitForFunction(()=>[...document.getElementById('groups').options].some(o=>o.textContent==='Piratas do Rocks'));await page.locator('#preview').click();await page.waitForFunction(()=>document.getElementById('preview-result').textContent.includes('Prévia de simulação'));
  if(process.env.MA_SCREENSHOT_DIR){await page.setViewportSize({width:1200,height:1000});await page.screenshot({path:process.env.MA_SCREENSHOT_DIR+'/portal-mensagem-automatica.png',fullPage:true});}
  await page.locator('#revoke').click();await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('revogada'));assert.equal(revoked,true);
  assert.equal(await page.evaluate(()=>localStorage.length+sessionStorage.length),0);assert.ok(calls.every(c=>!JSON.stringify(c).includes('Bearer')));assert.equal(requests.some(p=>p.startsWith('/v1')||p.includes('google')),false);
  await page.locator('#reveal-recovery').click();await page.waitForFunction(()=>document.getElementById('recovery-code').textContent.length===64);await page.evaluate(()=>window.dispatchEvent(new Event('pagehide')));assert.equal(await page.locator('#recovery-code').textContent(),'');assert.equal(await page.locator('#settings').isVisible(),false);
  await page.setViewportSize({width:320,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);
  console.log('Gestão local sintética: config automática, proxy nativo sem bearer, XSS, simulação, recuperação explícita, limpeza e 320px passaram.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
