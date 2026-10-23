/* NODE_PATH must expose the existing Playwright installation; no external requests. */
const {chromium}=require('playwright');
const fs=require('fs'),assert=require('assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><html><body><main id="root"></main></body></html>'}));
  await page.goto('http://mensagem-local.test');
  // Marcação mínima igual à do index.html: menu escondido, página do menu e o campo do código em Configurações.
  await page.evaluate(()=>{document.getElementById('root').innerHTML='<div id="mensagens-menu" hidden>Mensagens</div><input id="cfg-codigo"><button id="cfg-codigo-ok">Ativar</button><p id="cfg-codigo-status"></p>';
   window.state={mensagens_automaticas:false,admin_ia:false};window.managementConfig=null;window.portalResult={ok:true};window.adminCalls=0;window.claims=[];window.claimResult={ok:true};
   window.adminIaCarregar=()=>{window.adminCalls++;};window.toasts=[];window.toast=(m,e)=>window.toasts.push([m,e]);
   window.api={recursos_liberados:async()=>({...window.state}),assistente_estado:async()=>({context:{character_id:'Pirata Teste',world_id:'Antica'}}),
    mensagem_automatica_abrir_portal:async c=>{window.managementConfig=c;return window.portalResult;},
    liberar_recursos:async codigo=>{window.claims.push(codigo);if(window.claimResult.ok)window.state={mensagens_automaticas:true,admin_ia:true};return window.claimResult;}};});
  await page.addScriptTag({content:fs.readFileSync('web/mensagem_automatica.js','utf8')});
  await page.evaluate(()=>maAtualizar());
  assert.equal(await page.locator('#mensagens-menu').isHidden(),true,'sem liberação o menu não aparece');
  // código errado: mostra o erro e continua escondido
  await page.evaluate(()=>{window.claimResult={erro:'Código inválido ou já usado.'};});
  await page.locator('#cfg-codigo').fill('  codigo-errado  ');await page.locator('#cfg-codigo-ok').click();
  await page.waitForFunction(()=>document.getElementById('cfg-codigo-status').textContent.includes('inválido'));
  assert.deepEqual(await page.evaluate(()=>claims),['codigo-errado'],'o código é enviado sem espaços');assert.equal(await page.locator('#mensagens-menu').isHidden(),true);
  // código certo: menu aparece, Admin é reavaliado, campo é limpo
  await page.evaluate(()=>{window.claimResult={ok:true};});
  await page.locator('#cfg-codigo').fill('codigo-certo');await page.locator('#cfg-codigo-ok').click();
  await page.waitForFunction(()=>!document.getElementById('mensagens-menu').hidden);
  assert.equal(await page.locator('#cfg-codigo').inputValue(),'');assert.match(await page.locator('#cfg-codigo-status').textContent(),/aceito/);assert.ok(await page.evaluate(()=>adminCalls)>=2,'o menu Admin é reavaliado');
  // campo vazio não chama o servidor
  await page.locator('#cfg-codigo-ok').click();assert.equal(await page.evaluate(()=>claims.length),2);assert.match(await page.locator('#cfg-codigo-status').textContent(),/Cole o código/);
  // abrir a gestão leva as preferências salvas + personagem/mundo em uso
  await page.evaluate(()=>localStorage.setItem(maKey({personagem:'Pirata Teste',mundo:'Antica'}),JSON.stringify({blocks:{rashid:true},generateAt:'05:00'})));
  await page.evaluate(()=>maAbrir());await page.waitForFunction(()=>window.managementConfig);
  assert.deepEqual(await page.evaluate(()=>managementConfig),{blocks:{rashid:true},generateAt:'05:00',personagem:'Pirata Teste',mundo:'Antica'});
  await page.evaluate(()=>{window.managementConfig=null;window.portalResult={erro:'Este recurso ainda não está disponível.'};localStorage.setItem(maKey({personagem:'Pirata Teste',mundo:'Antica'}),'{bad json');});
  await page.waitForTimeout(1700);await page.evaluate(()=>maAbrir());await page.waitForFunction(()=>window.managementConfig);
  assert.deepEqual(await page.evaluate(()=>managementConfig),{personagem:'Pirata Teste',mundo:'Antica'},'storage inválido cai na identidade');
  await page.waitForFunction(()=>window.toasts.length);assert.match(await page.evaluate(()=>window.toasts[0][0]),/ainda não está disponível/);assert.equal(await page.evaluate(()=>window.toasts[0][1]),true,'erro vai como aviso de erro');
  // dois cliques seguidos abrem uma janela só
  await page.evaluate(()=>{window.opens=0;window.api.mensagem_automatica_abrir_portal=async()=>{window.opens++;return {ok:true};};});
  await page.waitForTimeout(1700);await page.evaluate(()=>Promise.all([maAbrir(),maAbrir()]));assert.equal(await page.evaluate(()=>opens),1);
  // a página "Mensagem do dia" não carrega mais o painel de mensagens automáticas
  const index=fs.readFileSync('web/index.html','utf8'),board=fs.readFileSync('web/world_board.js','utf8'),manifest=JSON.parse(fs.readFileSync('packaging-resources.json','utf8'));
  assert.ok(!board.includes('maPanel')&&!board.includes('maBind'));
  for(const id of ['mensagens-menu','cfg-codigo','cfg-codigo-ok'])assert.equal((index.match(new RegExp('id="'+id+'"','g'))||[]).length,1,id+' existe uma vez');
  assert.match(index,/id="mensagens-menu"[^>]*\shidden/,'o menu já nasce escondido');
  assert.ok(!index.includes('id="page-mensagens"')&&!index.includes('id="ma-abrir"'),'sem página nem botão intermediário');
  assert.match(index,/if \(pagina === 'mensagens'\) \{ if \(typeof maAbrir === 'function'\) maAbrir\(\); return; \}/,'clicar no menu abre direto a gestão');
  assert.ok(index.includes('<script src="mensagem_automatica.js"></script>'));assert.ok(manifest.files.includes('web/mensagem_automatica.js'));
  assert.deepEqual(errors,[]);console.log('Mensagens: menu escondido sem liberação, código errado/certo, Admin reavaliado, gestão com contexto, storage inválido, página sem painel antigo.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
