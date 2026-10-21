/* NODE_PATH must expose the existing Playwright installation; no external requests. */
const {chromium}=require('playwright');
const fs=require('fs'),assert=require('assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><html><body><main id="root"></main></body></html>'}));
  await page.goto('http://mensagem-local.test');
  const setup=async()=>{
   await page.addStyleTag({content:'*{box-sizing:border-box}body{margin:0;background:#171b22;color:#eee;font:14px sans-serif}#root{padding:12px;max-width:1000px;margin:auto}'+fs.readFileSync('web/world_board.css','utf8')+fs.readFileSync('web/mensagem_automatica.css','utf8')});
   await page.addScriptTag({content:`const $=id=>document.getElementById(id);const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const zbOpen=()=>'',zbDate=v=>v;const toast=()=>{};const zbLoad=()=>{};const api={zandaobot_mensagem:async(...args)=>{window.manualArgs=args;return {mensagem:'Mensagem manual original'};}};${fs.readFileSync('web/world_board.js','utf8')};window.render=r=>{window.context=r;$('root').innerHTML=wbPanel(r);wbBind(r);};`});
  };
  await setup();
  const r={personagem:'Pirata Teste',mundo:'Antica',dia:'2026-10-20'};
  await page.evaluate(r=>render(r),r);
  const manualBefore=await page.locator('#root').innerHTML();
  await page.addScriptTag({content:fs.readFileSync('web/mensagem_automatica.js','utf8')});
  await page.evaluate(r=>render(r),r);
  assert.equal(await page.locator('.wb-panel>.ma-panel').count(),1);
  assert.equal(await page.locator('#root').evaluate(e=>{const copy=e.cloneNode(true);copy.querySelector('.ma-panel').remove();return copy.innerHTML;}),manualBefore,'Manual markup unchanged');
  await page.locator('.wb-panel').evaluateAll(es=>es.forEach(e=>e.open=true));await page.locator('.ma-panel').evaluate(e=>e.open=true);
  assert.equal(await page.locator('[data-ma-value]').count(),9);assert.equal(await page.locator('[data-ma-arg]').count(),7);
  assert.equal(await page.locator('[data-ma-blocks]').count(),13);assert.equal(await page.locator('[data-ma-extras="mini"]').count(),0);
  const save=()=>page.locator('[data-ma-save]').click();
  const field=page.locator('[data-ma-value="comunidade"]');
  await field.fill('Piratas local');await page.locator('[data-ma-fields="comunidade"]').check();
  await page.locator('[data-ma-blocks="rashid"]').check();await page.locator('[data-ma-extras="guild"]').check();await page.locator('[data-ma-arg="guild"]').fill('Guild Teste');
  assert.equal(await page.locator('[data-wb-field="comunidade"]').inputValue(),'');
  await page.locator('[data-ma-time="generateAt"]').fill('09:00');await page.locator('[data-ma-time="sendAt"]').fill('08:00');await page.locator('[data-ma-zone]').fill('America/Cuiaba');
  await save();assert.match(await page.locator('[data-ma-status]').textContent(),/igual ou posterior/);
  assert.equal(await page.evaluate(()=>localStorage.getItem(maKey(context))),null);
  await page.locator('[data-ma-time="sendAt"]').fill('09:00');await page.locator('[data-ma-zone]').fill('Invalid/Zone');await save();assert.match(await page.locator('[data-ma-status]').textContent(),/Fuso inválido/);
  await page.locator('[data-ma-zone]').fill('');await save();assert.match(await page.locator('[data-ma-status]').textContent(),/Informe o fuso/);
  await page.locator('[data-ma-zone]').fill('Europe/Berlin');await save();assert.match(await page.locator('[data-ma-status]').textContent(),/envio automático ainda não está ativo/);
  const saved=await page.evaluate(()=>localStorage.getItem(maKey(context)));assert.equal(JSON.parse(saved).values.comunidade,'Piratas local');
  await page.reload();await setup();await page.addScriptTag({content:fs.readFileSync('web/mensagem_automatica.js','utf8')});await page.evaluate(r=>render(r),r);
  assert.equal(await field.inputValue(),'Piratas local');assert.equal(await page.locator('[data-ma-blocks="rashid"]').isChecked(),true);assert.equal(await page.locator('[data-ma-arg="guild"]').inputValue(),'Guild Teste');
  for(const other of [{...r,personagem:'Outro Player'},{...r,mundo:'Lobera'}]){await page.evaluate(r=>render(r),other);assert.equal(await field.inputValue(),'');assert.equal(await page.locator('[data-ma-time="generateAt"]').inputValue(),'');}
  await page.evaluate(r=>render({...r,personagem:' pirata teste ',mundo:'ANTICA'}),r);assert.equal(await field.inputValue(),'Piratas local','Identity normalized');
  await page.evaluate(r=>{MA_DRAFTS.clear();localStorage.setItem(maKey(r),'{bad json');render(r);},r);assert.match(await page.locator('[data-ma-status]').textContent(),/Não foi possível carregar/);assert.equal(await field.inputValue(),'');
  await page.evaluate(r=>{localStorage.setItem(maKey(r),JSON.stringify({values:{comunidade:'"><img src=x onerror="window.pwned=1">'},timezone:'"><img src=x onerror="window.pwned=1">'}));render(r);},r);
  assert.equal(await page.locator('.ma-panel img').count(),0);assert.equal(await page.evaluate(()=>window.pwned),undefined);assert.match(await field.inputValue(),/<img/);
  await page.evaluate(r=>{localStorage.removeItem(maKey(r));render(r);},r);await page.locator('.wb-panel').evaluateAll(es=>es.forEach(e=>e.open=true));await page.locator('.ma-panel').evaluate(e=>e.open=true);
  await page.evaluate(()=>{window.originalSetItem=Storage.prototype.setItem;Storage.prototype.setItem=()=>{throw new DOMException('quota','QuotaExceededError');};});await save();assert.match(await page.locator('[data-ma-status]').textContent(),/Não foi possível salvar/);await page.evaluate(()=>Storage.prototype.setItem=window.originalSetItem);
  await page.evaluate(()=>{MA_DRAFTS.clear();window.originalGetItem=Storage.prototype.getItem;Storage.prototype.getItem=()=>{throw new DOMException('blocked','SecurityError');};render(context);});assert.match(await page.locator('[data-ma-status]').textContent(),/Não foi possível carregar/);await page.evaluate(()=>Storage.prototype.getItem=window.originalGetItem);
  await page.evaluate(()=>render(context));await page.locator('.wb-panel').evaluateAll(es=>es.forEach(e=>e.open=true));await page.locator('.ma-panel').evaluate(e=>e.open=true);await save();assert.match(await page.locator('[data-ma-status]').textContent(),/Configuração salva/,'Empty schedule saves draft');
  await page.locator('[data-wb-field="comunidade"]').fill('Manual intacta');await page.locator('#wb-generate').click();assert.equal(await page.locator('#wb-message').inputValue(),'Mensagem manual original');assert.equal(await page.evaluate(()=>manualArgs[1].comunidade),'Manual intacta');assert.equal(await page.evaluate(()=>manualArgs[3]),fs.readFileSync('web/world_board.js','utf8').includes('WB_TICKS')?true:undefined,'Original World Board flag unchanged');
  for(const width of [1200,320]){
   await page.setViewportSize({width,height:1000});await page.locator('.ma-panel').evaluate(e=>e.open=true);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`No overflow at ${width}px`);
   if(process.env.MA_SCREENSHOT_DIR){await page.locator('.ma-panel').screenshot({path:process.env.MA_SCREENSHOT_DIR+(width===1200?'/mensagem-automatica.png':'/mensagem-automatica-mobile.png')});}
  }
  await field.fill('Rascunho não salvo');await page.evaluate(()=>render(context));assert.equal(await field.inputValue(),'Rascunho não salvo','Background refresh preserves draft');await page.evaluate(r=>render({...r,personagem:'Outro'}),r);assert.equal(await field.inputValue(),'');await page.evaluate(r=>render(r),r);assert.equal(await field.inputValue(),'Rascunho não salvo');
  const index=fs.readFileSync('web/index.html','utf8'),manifest=JSON.parse(fs.readFileSync('packaging-resources.json','utf8'));assert.ok(index.includes('<script src="mensagem_automatica.js"></script>'));assert.ok(manifest.files.includes('web/mensagem_automatica.js'));
  assert.deepEqual(errors,[]);console.log('Mensagem automática: real wbPanel integration, unchanged manual flow, 9 variables/7 extras, persistence/reload/context, validation/storage/escaping, 1200/320px passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
