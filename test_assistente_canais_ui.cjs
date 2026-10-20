const {chromium}=require('playwright');
const fs=require('fs'),assert=require('assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('https://**/*',r=>r.abort());
  const html=fs.readFileSync('web/index.html','utf8'),section=html.slice(html.indexOf('<section class="page" id="page-voz">'),html.indexOf('<!-- ================= TIMERS DE ÁUDIO'));
  async function load(saved=null,blocked=false){
   await page.goto('about:blank');
   const styles=[...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map(m=>m[1]).join('\n');
   await page.setContent(`<style>${styles}*{box-sizing:border-box}body{margin:0;display:block;overflow:auto}#page-voz{padding:10px;min-width:0;display:block}.page{width:100%;max-width:none}.voz-form{display:flex;flex-wrap:wrap;gap:8px}.voz-form label{flex:1 1 160px}input,select{max-width:100%}${fs.readFileSync('web/assistente.css','utf8')}</style>${section}`);
   await page.locator('#page-voz').evaluate(e=>e.classList.add('shown'));
   await page.addScriptTag({content:`const PERS_OUVINTES=[];const MEUS={atual:'Test Knight',lista:[{nome:'Test Knight',mundo:'Antica'}]};window.abrirUpo=()=>{};window.fixture={personagens:[],up:[],death:[]};window.actions=[];window.pywebview={api:{
    assistente_estado:async()=>({context:{character_id:'Test Knight',world_id:'Antica',level:100},timers:[],catalog:{bosses:[]},log:[]}),
    assistente_executar:async(intent,args)=>{window.actions.push({intent,args});return intent==='stamina.get'?{erro:'Registre uma referência'}:intent==='boss.cooldown.list'?{bosses:[]}:{message:'Feito'};},
    assistente_chat:async()=>({resposta:'Resposta de teste'}),assistente_chat_limpar:async()=>({ok:true}),
    conversao_tc_carregar:async()=>({valores:{gold_por_tc:46600,tc_pacote:250,reais_pacote:50},automatico:false}),
    assistente_monitor_estado:async()=>window.fixture,
    assistente_monitor_configurar:async(nome,up,death,remove)=>{window.fixture.personagens=remove?[]:[{nome,up,death,estado:'Aguardando consulta'}];return window.fixture;}
   }};window.testStore=${JSON.stringify(saved)};Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:key=>window.testStore,setItem:(key,value)=>{window.testStore=value;},removeItem:()=>{window.testStore=null;}}});${blocked?"Object.defineProperty(window,'localStorage',{configurable:true,get(){throw new Error('blocked')}});":''}`});
   await page.addScriptTag({content:`window.intervalLengths=[];window.originalInterval=window.setInterval;window.setInterval=(fn,ms)=>{window.intervalLengths.push(ms);return window.originalInterval(fn,ms);};`});
   for(const script of ['assistente_ferramentas.js','assistente.js','chat.js','assistente_canais.js'])await page.addScriptTag({content:fs.readFileSync('web/'+script,'utf8')});
   await page.waitForTimeout(30);
  }
  await load();
  if(process.env.ASSISTENTE_SCREENSHOT_DIR){await page.setViewportSize({width:1400,height:900});await page.screenshot({path:process.env.ASSISTENTE_SCREENSHOT_DIR+'/assistente-canais-default.png'});}
  const ids=()=>page.locator('.chat-canais [role=tab]').evaluateAll(es=>es.map(e=>e.id.replace('chat-canal-','')));
  assert.deepEqual(await ids(),['local','log','up','death','help','ia']);
  assert.ok(await page.evaluate(()=>window.intervalLengths.includes(1000)),'Estado do monitor é lido localmente a cada segundo');
  assert.equal(await page.locator('.assistente-nav').count(),1);
  async function open(id){if(await page.locator(`[data-assistente-tab=${id}]`).count()){await page.click(`[data-assistente-tab=${id}]`);return;}await page.click('[data-assistente-tab=overview]');await page.click('#assistente-canal-abrir');await page.selectOption('#assistente-canal-lista',id);await page.locator('#assistente-canal-dialog button').first().click();}
  await open('shared');await page.click('#shared-mode-party');await page.fill('#shared-levels','200,300');await open('market');
  assert.deepEqual(await ids(),['local','log','up','death','help','ia']);
  assert.equal(await page.locator('[data-assistente-panel=market]').isVisible(),true);
  await open('shared');
  assert.equal(await page.inputValue('#shared-levels'),'200,300');
  await open('shared');assert.equal((await ids()).includes('shared'),false);
  for(const id of ['timers','upo','bosstiary','bosses','stamina','market']){await open(id);assert.equal(await page.locator(`[data-assistente-panel=${id}]`).isVisible(),true);assert.equal(await page.locator(`[data-assistente-panel=${id}]`).evaluate(e=>e.closest('.chat')===null),true);}
  assert.equal((await ids()).at(-1),'ia');
  await page.click('[data-assistente-tab=overview]');await page.getByLabel('Fechar canal Help',{exact:true}).click();await page.click('#chat-canal-ia');
  await page.fill('#chat-texto','Olá');await page.locator('#chat-form button[type=submit]').click();await page.waitForTimeout(20);assert.match(await page.locator('#chat-mensagens').innerText(),/Resposta de teste/);
  await open('help');assert.equal(await page.locator('#assistente-instrucoes').isVisible(),true);
  await page.click('#assistente-canal-abrir');await page.keyboard.press('Escape');assert.equal(await page.locator('#assistente-canal-dialog').isVisible(),false);assert.equal(await page.evaluate(()=>document.activeElement.id),'assistente-canal-abrir');
  await page.click('#chat-canal-ia');
  await page.evaluate(()=>{window.fixture.up=[{id:'one',at:'2026-10-20T10:00:00Z',texto:'🛡️ Test Knight subiu do level 100 para 101 · horário da detecção.'}];return assistenteCanais.refreshMonitor();});
  assert.match(await page.locator('#chat-canal-up').innerText(),/\(1\)/);await page.click('#chat-canal-up');assert.equal(await page.locator('#chat-canal-up').innerText(),'UP Level');assert.match(await page.locator('#assistente-painel-up').innerText(),/100 para 101/);
  if(process.env.ASSISTENTE_SCREENSHOT_DIR)await page.screenshot({path:process.env.ASSISTENTE_SCREENSHOT_DIR+'/assistente-canais-up.png'});
  await page.getByLabel('Fechar canal UP Level',{exact:true}).click();
  await page.evaluate(()=>{window.fixture.up.push({id:'two',at:'2026-10-20T11:00:00Z',texto:'Test Knight subiu do level 101 para 102 · horário da detecção.'});return assistenteCanais.refreshMonitor();});
  await open('up');assert.equal(await page.locator('#chat-canal-up').innerText(),'UP Level');assert.match(await page.locator('#assistente-painel-up').innerText(),/101 para 102/);
  await open('market');
  await page.evaluate(()=>{window.fixture.up.push({id:'three',at:'2026-10-20T12:00:00Z',texto:'Test Knight subiu do level 102 para 103 · horário da detecção.'});return assistenteCanais.refreshMonitor();});
  assert.match(await page.locator('#chat-canal-up').innerText(),/\(1\)/);await page.click('[data-assistente-tab=overview]');await page.waitForTimeout(20);assert.equal(await page.locator('#chat-canal-up').innerText(),'UP Level');
  await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});window.fixture.up.push({id:'four',at:'2026-10-20T13:00:00Z',texto:'Test Knight subiu do level 103 para 104 · horário da detecção.'});return assistenteCanais.refreshMonitor();});
  assert.match(await page.locator('#chat-canal-up').innerText(),/\(1\)/);await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));});assert.equal(await page.locator('#chat-canal-up').innerText(),'UP Level');
  await open('shared');await page.evaluate(()=>chatEstado({context:{character_id:'Other Player',world_id:'Secura'},log:[]}));await page.waitForTimeout(20);assert.equal(await page.locator('[data-assistente-panel=shared]').isVisible(),true);assert.equal(await page.locator('#chat-mensagens').isVisible(),false);assert.equal(await page.inputValue('#shared-levels'),'200,300');
  await page.click('[data-assistente-tab=overview]');await page.locator('#chat-canal-up').focus();await page.keyboard.press('End');assert.equal(await page.locator('#chat-canal-ia').getAttribute('aria-selected'),'true');
  const context=await page.evaluate(async()=>{
   const api=window.pywebview.api,original=api.assistente_estado,pending=[];api.assistente_estado=()=>new Promise(resolve=>pending.push(resolve));
   const older=window.assistenteLoad(),newer=window.assistenteLoad();
   const result=name=>({context:{character_id:name,world_id:'Antica',level:100},timers:[],catalog:{bosses:[]},log:[]});
   pending[1](result('Newer Player'));await newer;pending[0](result('Older Player'));await older;api.assistente_estado=original;return document.getElementById('assistente-context').textContent;
  });assert.match(context,/Newer Player/);assert.doesNotMatch(context,/Older Player/);
  await page.evaluate(()=>{
   const api=window.pywebview.api;window.oldApi={estado:api.assistente_estado,executar:api.assistente_executar};window.raceName='Old Profile';window.pendingBoss=[];
   api.assistente_estado=async()=>({context:{character_id:window.raceName,world_id:'Antica',level:100},timers:[],catalog:{bosses:[]},log:[]});
   api.assistente_executar=(intent,args,context)=>intent==='boss.cooldown.list'?new Promise(resolve=>window.pendingBoss.push({resolve,context})):window.oldApi.executar(intent,args,context);
   window.assistenteSelect('bosstiary');
  });await page.waitForFunction(()=>window.pendingBoss.length===1);
  await page.evaluate(()=>{window.raceName='New Profile';window.assistenteLoad();});await page.waitForFunction(()=>window.pendingBoss.length===2);
  await page.evaluate(()=>window.pendingBoss[1].resolve({bosses:[{boss_id:'new',name:'New Boss',aliases:[],category:'bane',goals:[25,100,300],progress:1,next_goal:25,missing:24,cooldown_minutes:1200}]}));await page.waitForTimeout(20);
  await page.evaluate(()=>window.pendingBoss[0].resolve({bosses:[{boss_id:'old',name:'Old Boss',aliases:[],category:'bane',goals:[25,100,300],progress:1,next_goal:25,missing:24,cooldown_minutes:1200}]}));await page.waitForTimeout(20);
  assert.match(await page.locator('#bosstiary-lista').innerText(),/New Boss/);assert.doesNotMatch(await page.locator('#bosstiary-lista').innerText(),/Old Boss/);
  await page.evaluate(()=>{window.pywebview.api.assistente_estado=window.oldApi.estado;window.pywebview.api.assistente_executar=window.oldApi.executar;window.assistenteSelect('overview');});
  await page.click('#assistente-monitor-abrir');await page.fill('#assistente-monitor-nome','Other Player');await page.locator('.monitor-adicionar button').click();await page.waitForTimeout(20);assert.match(await page.locator('#assistente-monitor-lista').innerText(),/Other Player/);assert.match(await page.locator('#assistente-monitor-lista').innerText(),/Última verificação/);assert.match(await page.locator('#assistente-monitor-dialog').innerText(),/cache da fonte de até 5 min/);await page.keyboard.press('Escape');
  await page.click('#chat-canal-up');const saved=await page.evaluate(()=>window.testStore);assert.ok(!saved.includes('Other Player'));await load(saved);assert.equal(await page.locator('#chat-canal-up').getAttribute('aria-selected'),'true');assert.equal((await ids()).at(-1),'ia');
  for(const width of [1400,320]){
   await page.setViewportSize({width,height:900});await page.click('[data-assistente-tab=overview]');await page.click('#chat-canal-ia');assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   if(process.env.ASSISTENTE_SCREENSHOT_DIR){await page.screenshot({path:process.env.ASSISTENTE_SCREENSHOT_DIR+`/assistente-canais-chat-${width}.png`});if(width===1400){await page.click('#assistente-canal-abrir');await page.screenshot({path:process.env.ASSISTENTE_SCREENSHOT_DIR+'/assistente-canais-abrir.png'});await page.keyboard.press('Escape');await page.click('#assistente-monitor-abrir');await page.screenshot({path:process.env.ASSISTENTE_SCREENSHOT_DIR+'/assistente-canais-monitor.png'});await page.keyboard.press('Escape');}}
   await open('shared');assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   if(process.env.ASSISTENTE_SCREENSHOT_DIR)await page.screenshot({path:process.env.ASSISTENTE_SCREENSHOT_DIR+`/assistente-canais-tool-${width}.png`});
   await open('help');const visible=await page.locator('#chat-canal-ia').boundingBox();assert.ok(visible.x>=0&&visible.x+visible.width<=width);assert.equal(await page.locator('#assistente-canal-abrir').isVisible(),true);const active=await page.locator('#chat-canal-help').boundingBox(),viewport=await page.locator('.assistente-canais-scroll').boundingBox();assert.ok(active.x>=viewport.x&&active.x+active.width<=visible.x,'A aba ativa fica visível sem ser coberta por Tudo IA');
  }
  await load(JSON.stringify({abertos:['local','log','timers','market','ia'],atual:'market'}));assert.deepEqual(await ids(),['local','log','up','death','help','ia']);assert.equal(await page.locator('#chat-canal-ia').getAttribute('aria-selected'),'true');
  await load('{broken');assert.deepEqual(await ids(),['local','log','up','death','help','ia']);await load(null,true);assert.deepEqual(await ids(),['local','log','up','death','help','ia']);
  assert.deepEqual(errors,[]);console.log('Assistant channels: real DOM, tools preserved, close/reopen, IA pinned, monitor/unread, persistence, dialogs, chat and 1400/320px passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
