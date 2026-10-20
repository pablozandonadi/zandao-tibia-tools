/* Run with Playwright in NODE_PATH; CHROME_PATH may select installed Chrome. */
const {chromium}=require('playwright');
const fs=require('fs'),assert=require('assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  // Official image requests are mocked with a bundled public sprite; no external requests.
  await page.route('https://**/*',route=>route.request().url().startsWith('https://static.tibia.com/images/news/')?route.fulfill({contentType:'image/gif',body:fs.readFileSync('web/assets/zandaobot/rashid.gif')}):route.abort());
  const index=fs.readFileSync('web/index.html','utf8'),globalStyles=[...index.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map(m=>m[1]).join('\n');
  await page.setContent(`<style>${globalStyles}body{display:block;overflow:auto;height:auto}#page-zandaobot{display:block;padding:12px;max-width:none}${fs.readFileSync('web/assistente.css','utf8')}${fs.readFileSync('web/zandaobot.css','utf8')}</style><main id="page-zandaobot"><div id="zb-result"></div></main>${['world','find','active','refresh','follow','worlds'].map(id=>`<input id="zb-${id}">`).join('')}`);
  await page.addScriptTag({content:`const $=id=>document.getElementById(id);const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const PERS_OUVINTES=[],WB={dirty:false};let api=null;function wbPanel(){return ''}function wbBind(){};${fs.readFileSync('web/zandaobot.js','utf8')}`});
  const bosses=['Maxxenius','Alptramun','Izcandar the Banished','Plagueroot','Malofur Mangrinder'];
  const data={mundo:'Xybra',dia:'2026-10-20',consulta:'2026-10-20T15:00:00Z',noticias_consulta:1792508400,anuncios_consulta:1792508400,news_ticker_consulta:1792508400,server_save_ms:Date.parse('2026-10-21T08:00:00Z'),rashid:'Darashia',dream_court:{nome:'Maxxenius'},yasir:{estado:'ausente',mundos_com_yasir:['Antica','Secura']},
   killstatistics:{estado:'disponivel',mundo:'Xybra',consulta:1792508400,processamento:'2026-10-20T14:03:02Z',bosses:bosses.map((nome,i)=>({nome,last_day_killed:i===2?null:i,last_week_killed:i+10}))},
   calendario:{estado:'disponivel',eventos:[{titulo:'Annual Autumn Vintage',inicio:'2026-10-17',fim:'2026-10-24',estado:'ativo',escopo:'Todos os mundos',server_save:true},{titulo:'Halloween Event',inicio:'2026-10-31',fim:'2026-11-03',estado:'proximo',escopo:'Todos os mundos',server_save:true}]},
   noticias:Array.from({length:8},(_,i)=>({id:9024-i,titulo:i===0?'Balancing, Fixes and Changes':['Technical Update','New Features','Maintenance Completed','Client Improvements','Gameplay Adjustments','Development Update','Service Update'][i-1],data:`2026-10-${20-i}`,categoria:i%2?'technical':'development',imagem:'https://static.tibia.com/images/news/news_fixes_243x200.png'})),
   anuncios:[{id:9001,titulo:'Orcsoberfest',data:'2026-10-07',categoria:'community'},{id:9000,titulo:'Annual Autumn Vintage',data:'2026-10-01',categoria:'community'}],
   news_ticker:Array.from({length:10},(_,i)=>({id:9100-i,data:`2026-10-${20-Math.floor(i/2)}`,texto:i===0?'With today’s server save, several fixes have been implemented. '+ 'A'.repeat(320):['Maintenance completed successfully.','A new client version is available.','Changes to hunting grounds are now live.','The affected game worlds are back online.','Scheduled maintenance has ended.'][i%5]}))};
  const render=async d=>page.evaluate(d=>zbRender(d),d);
  for(const width of [1400,1000,320]){
   await page.setViewportSize({width,height:1000});await page.evaluate(()=>{ZB.open={};document.getElementById('zb-result').replaceChildren();});await render(data);
   assert.deepEqual(await page.locator('.zb-news-panel h2').allTextContents(),['News','Eventos do Tibia']);
   assert.equal(await page.locator('.zb-worlds').isVisible(),true);
   const position=await page.locator('.zb-news-wide').evaluate(e=>({next:e.previousElementSibling.classList.contains('zb-worlds'),top:e.getBoundingClientRect().top,yasirBottom:e.previousElementSibling.getBoundingClientRect().bottom,yasirTop:e.previousElementSibling.getBoundingClientRect().top,metaBottom:document.querySelector('.zb-meta').getBoundingClientRect().bottom}));
   assert.equal(position.next,true,'News fica logo após Yasir em outros mundos');assert.ok(position.top>position.yasirBottom);assert.ok(position.yasirTop>position.metaBottom);
   assert.equal(await page.locator('.zb-news-day').count(),0);
   assert.equal(await page.locator('.zb-news-ticker').count(),10);
   assert.deepEqual(await Promise.all(Array.from({length:10},(_,i)=>page.locator('.zb-news-ticker').nth(i).isVisible())),[true,true,true,true,true,false,false,false,false,false]);
   assert.deepEqual(await page.locator('.zb-news-ticker').evaluateAll(es=>es.map(e=>e.open)),Array(10).fill(false));
   assert.deepEqual(await page.locator('.zb-ticker-date').allTextContents(),data.news_ticker.map(x=>x.data.split('-').reverse().join('/')));
   const featured=page.locator('.zb-news-featured');assert.match(await featured.innerText(),/Balancing, Fixes and Changes/);
   assert.equal(await featured.locator('a').getAttribute('href'),'https://www.tibia.com/news/?subtopic=newsarchive&id=9024');
   assert.equal(await featured.locator('img').isVisible(),true);
   assert.equal(await page.locator('.zb-news-archive').evaluate(e=>e.open),false);
   assert.equal(await page.locator('.zb-news-archive .zb-news').count(),7);
   assert.equal(await page.locator('.zb-news-archive .zb-news').first().isVisible(),false);
   const layout=await page.evaluate(()=>{const rect=e=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:r.width,height:r.height};};return {news:rect(document.querySelector('.zb-news-wide')),grid:rect(document.querySelector('.zb-feed-grid')),calendar:rect(document.querySelector('.zb-feed-grid>.zb-calendar')),events:rect(document.querySelector('.zb-feed-grid>.zb-news-panel')),tickers:[...document.querySelectorAll('.zb-news-ticker')].filter(e=>!e.closest('.zb-ticker-more:not([open])')).map(rect),feature:rect(document.querySelector('.zb-news-featured'))};});
   assert.ok(layout.news.bottom<layout.grid.top);assert.ok(Math.abs(layout.news.width-layout.grid.width)<1);
   if(width>900){assert.equal(layout.calendar.top,layout.events.top);assert.ok(layout.calendar.left<layout.events.left);assert.ok(layout.news.height<750);}
   for(let i=1;i<5;i++)assert.ok(layout.tickers[i].top>=layout.tickers[i-1].bottom);
   assert.ok(layout.feature.top>=layout.tickers[4].bottom);
   const preview=await page.locator('.zb-ticker-preview').first().evaluate(e=>({scroll:e.scrollWidth,client:e.clientWidth,whiteSpace:getComputedStyle(e).whiteSpace}));assert.equal(preview.whiteSpace,'nowrap');assert.ok(preview.scroll>preview.client,'Long preview uses ellipsis');
   const ticker=page.locator('.zb-news-ticker').first();await ticker.locator('summary').focus();await page.keyboard.press('Enter');assert.equal(await ticker.evaluate(e=>e.open),true);
   assert.equal(await ticker.locator('.zb-ticker-content p').innerText(),data.news_ticker[0].texto);
   assert.equal(await page.locator('.zb-news-ticker').nth(1).evaluate(e=>e.open),false);
   assert.equal(await page.locator('.zb-ticker-more').evaluate(e=>e.open),false);await page.locator('.zb-ticker-more>summary').click();assert.equal(await page.locator('.zb-news-ticker').last().isVisible(),true);
   await page.locator('.zb-news-archive summary').click();assert.equal(await page.locator('.zb-news-archive .zb-news').last().isVisible(),true);
   await render(data);assert.equal(await page.locator('[data-zb-key="news-ticker-9100"]').evaluate(e=>e.open),true);assert.equal(await page.locator('[data-zb-key="news-archive"]').evaluate(e=>e.open),true);assert.equal(await page.locator('[data-zb-key="news-ticker-more"]').evaluate(e=>e.open),true);
   const immediate=await page.evaluate(d=>{const key='news-ticker-9099',selector=`[data-zb-key="${key}"]`;document.querySelector(selector).open=true;zbRender(d);const opened=document.querySelector(selector).open;document.querySelector(selector).open=false;zbRender(d);return {opened,closed:!document.querySelector(selector).open};},data);
   assert.deepEqual(immediate,{opened:true,closed:true},'Refresh imediato preserva o DOM sem esperar pelo evento toggle');
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   await page.locator('.zb-news-archive summary').click();
   if(process.env.NEWS_SCREENSHOT_DIR&&width===1400){await page.locator('.zb-news-wide').scrollIntoViewIfNeeded();await page.screenshot({path:process.env.NEWS_SCREENSHOT_DIR+'/news-home-tibia-expandida.png'});}
   await page.locator('.zb-news-ticker summary').first().click();
   await page.locator('.zb-ticker-more>summary').click();
   if(process.env.NEWS_SCREENSHOT_DIR&&width!==1000){await page.locator('.zb-news-wide').scrollIntoViewIfNeeded();await page.screenshot({path:process.env.NEWS_SCREENSHOT_DIR+(width===1400?'/news-home-tibia-compacta.png':'/news-home-tibia-320.png')});}
   const image=page.locator('.zb-news-featured img');await image.dispatchEvent('error');assert.equal(await image.isVisible(),false);assert.equal(await page.locator('.zb-news-featured .zb-news-fallback').isVisible(),true);
   await page.locator('.zb-kills').evaluate(e=>e.open=true);assert.equal(await page.locator('.zb-kills tbody tr').count(),5);assert.equal(await page.locator('.zb-kills tbody tr').nth(0).locator('td').first().innerText(),'0');assert.equal(await page.locator('.zb-kills tbody tr').nth(2).locator('td').first().innerText(),'—');assert.match(await page.locator('.zb-kills').innerText(),/Processamento no TibiaData/);
  }
  for(const [estado,velho,expected] of [['desatualizado',true,'consulta anterior'],['indisponivel',false,'indisponível'],['selecionar_mundo',false,'Escolha um mundo']]){await render({...data,killstatistics:{...data.killstatistics,estado,velho}});await page.locator('.zb-kills').evaluate(e=>e.open=true);assert.match(await page.locator('.zb-kills').innerText(),new RegExp(expected));}
  await render({...data,noticias:[]});assert.equal(await page.locator('.zb-news-ticker').count(),10);assert.equal(await page.locator('.zb-news-featured').count(),0);assert.match(await page.locator('.zb-news-wide').innerText(),/Nenhuma notícia disponível/);
  await render({...data,noticias:[{id:'x" onclick="window.pwned=1',titulo:'<img src=x onerror="window.pwned=1">',data:'2026-10-20',imagem:'https://evil.example/x.png'}],news_ticker:[{id:-1,data:'bad',texto:'<script>window.pwned=1</script>'}],noticias_velhas:true,news_ticker_velho:true});
  assert.equal(await page.locator('.zb-news-wide').locator('img, a, script').count(),0);assert.equal(await page.locator('[data-zb-key="news-ticker-unknown-0"]').count(),1);assert.match(await page.locator('.zb-news-wide').innerText(),/Dados anteriores/);assert.match(await page.locator('.zb-news-wide').innerText(),/News Ticker:.*dados anteriores/);assert.equal(await page.evaluate(()=>window.pwned),undefined);
  await render({...data,noticias:[],news_ticker:[],anuncios:[]});assert.match(await page.locator('#zb-result').innerText(),/Nenhuma notícia disponível/);assert.match(await page.locator('#zb-result').innerText(),/Nenhum aviso disponível/);assert.match(await page.locator('#zb-result').innerText(),/Nenhum anúncio disponível/);
  assert.deepEqual(errors,[]);console.log('ZandaoBot: compact vertical tickers, featured news/archive, safe links/images, preserved expansions, fallbacks and 1400/1000/320px passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
