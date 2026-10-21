/* NODE_PATH must expose the existing Playwright installation; no external requests. */
const {chromium}=require('playwright');
const fs=require('fs'),assert=require('assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><html><body><main id="root"></main></body></html>'}));
  await page.goto('http://mensagem-local.test');
  await page.addStyleTag({content:'*{box-sizing:border-box}body{margin:0;background:#171b22;color:#eee;font:14px sans-serif}#root{padding:12px;max-width:1000px;margin:auto}'+fs.readFileSync('web/world_board.css','utf8')+fs.readFileSync('web/mensagem_automatica.css','utf8')});
  await page.addScriptTag({content:`const $=id=>document.getElementById(id);const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const zbOpen=()=>'',zbDate=v=>v;const toast=()=>{};const zbLoad=()=>{};const api={mensagem_automatica_abrir_portal:async c=>{window.managementConfig=c;return window.portalResult||{ok:true};},zandaobot_mensagem:async(...args)=>{window.manualArgs=args;return {mensagem:'Mensagem manual original'};}};${fs.readFileSync('web/world_board.js','utf8')};window.render=r=>{window.context=r;$('root').innerHTML=wbPanel(r);wbBind(r);};`});
  const r={personagem:'Pirata Teste',mundo:'Antica',dia:'2026-10-20'};
  await page.evaluate(r=>render(r),r);
  const manualBefore=await page.locator('#root').innerHTML();
  await page.addScriptTag({content:fs.readFileSync('web/mensagem_automatica.js','utf8')});
  await page.evaluate(r=>render(r),r);
  assert.equal(await page.locator('.wb-panel>.ma-panel').count(),1);
  assert.equal(await page.locator('#root').evaluate(e=>{const copy=e.cloneNode(true);copy.querySelector('.ma-panel').remove();return copy.innerHTML;}),manualBefore,'Manual markup unchanged');
  await page.locator('.wb-panel').evaluateAll(es=>es.forEach(e=>e.open=true));
  // Atalho: abre a tela única com as preferências salvas + personagem/mundo em uso.
  await page.evaluate(r=>localStorage.setItem(maKey(r),JSON.stringify({blocks:{rashid:true},generateAt:'05:00'})),r);
  await page.locator('[data-ma-portal]').click();await page.waitForFunction(()=>window.managementConfig);
  assert.deepEqual(await page.evaluate(()=>managementConfig),{blocks:{rashid:true},generateAt:'05:00',personagem:'Pirata Teste',mundo:'Antica'});
  await page.evaluate(r=>{window.managementConfig=null;window.portalResult={erro:'Portal sintético indisponível.'};localStorage.setItem(maKey(r),'{bad json');},r);
  await page.locator('[data-ma-portal]').click();await page.waitForFunction(()=>window.managementConfig);
  assert.deepEqual(await page.evaluate(()=>managementConfig),{personagem:'Pirata Teste',mundo:'Antica'},'Bad storage falls back to identity only');
  assert.match(await page.locator('[data-ma-status]').textContent(),/Portal sintético/);
  await page.locator('[data-wb-field="comunidade"]').fill('Manual intacta');await page.locator('#wb-generate').click();assert.equal(await page.locator('#wb-message').inputValue(),'Mensagem manual original');assert.equal(await page.evaluate(()=>manualArgs[1].comunidade),'Manual intacta');
  for(const width of [1200,320]){await page.setViewportSize({width,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`No overflow at ${width}px`);}
  const index=fs.readFileSync('web/index.html','utf8'),manifest=JSON.parse(fs.readFileSync('packaging-resources.json','utf8'));assert.ok(index.includes('<script src="mensagem_automatica.js"></script>'));assert.ok(manifest.files.includes('web/mensagem_automatica.js'));
  assert.deepEqual(errors,[]);console.log('Mensagem automática: atalho da tela única, manual intacta, preferências/identidade, storage inválido, 1200/320px passaram.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
