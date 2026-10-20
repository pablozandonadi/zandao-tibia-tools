/* Run with Playwright in NODE_PATH; CHROME_PATH may select installed Chrome. */
const {chromium}=require('playwright');
const fs=require('fs');
const assert=require('assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 try {
  const page=await browser.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('https://**/*',r=>r.abort());
  await page.setContent(`<style>*{box-sizing:border-box}body{margin:0;background:#15191f;color:#ddd;font-family:Arial}#page-zandaobot{padding:12px;--ink-dim:#aab;--surface:#20252c;--font-body:Arial}${fs.readFileSync('web/zandaobot.css','utf8')}</style><main id="page-zandaobot"><div id="zb-result"></div></main>${['world','find','active','refresh','follow','worlds'].map(id=>`<input id="zb-${id}">`).join('')}`);
  await page.addScriptTag({content:`const $=id=>document.getElementById(id); const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const PERS_OUVINTES=[],WB={dirty:false};let api=null;function wbPanel(){return ''}function wbBind(){};${fs.readFileSync('web/zandaobot.js','utf8')}`});
  const bosses=['Maxxenius','Alptramun','Izcandar the Banished','Plagueroot','Malofur Mangrinder'];
  const data={mundo:'Xybra',dia:'2026-10-15',consulta:'2026-10-15T15:00:00Z',dream_court:{nome:'Maxxenius'},killstatistics:{estado:'disponivel',mundo:'Xybra',consulta:1792076400,processamento:'2026-10-15T14:03:02Z',bosses:bosses.map((nome,i)=>({nome,last_day_killed:i===2?null:i,last_week_killed:i+10}))},
   noticias:[{id:9024,titulo:'Balancing, Fixes and Changes',data:'2026-10-20',categoria:'development',imagem:'https://static.tibia.com/images/news/news_fixes_243x200.png'},
    {id:9010,titulo:'Technical Update',data:'2026-10-18',categoria:'technical'}],
   anuncios:[{id:9001,titulo:'Orcsoberfest',data:'2026-10-07',categoria:'community'}],
   news_ticker:[{id:9025,data:'2026-10-20',texto:'Maintenance completed.'},{id:9027,data:'2026-10-20',texto:'Second notice.'},{id:9026,data:'2026-10-19',texto:'Only a ticker today.'}]};
  for(const width of [1400,1000,320]){
   await page.setViewportSize({width,height:1000});
   await page.evaluate(d=>zbRender(d),data);
   await page.locator('.zb-kills').evaluate(e=>e.open=true);
   assert.equal(await page.locator('.zb-kills tbody tr').count(),5);
   assert.equal(await page.locator('.zb-kills tbody tr').nth(0).locator('td').first().innerText(),'0');
   assert.equal(await page.locator('.zb-kills tbody tr').nth(2).locator('td').first().innerText(),'—');
   assert.match(await page.locator('.zb-kills').innerText(),/Processamento no TibiaData/);
   assert.match(await page.locator('.zb-kills').innerText(),/não confirma o boss atual/);
   assert.deepEqual(await page.locator('.zb-news-panel h2').allTextContents(),['News','Eventos do Tibia']);
   assert.deepEqual(await page.locator('.zb-news-day h3').allTextContents(),['20/10/2026','19/10/2026','18/10/2026']);
   const layout=await page.evaluate(()=>{const rect=q=>{const r=document.querySelector(q).getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,width:r.width};};return {news:rect('.zb-news-wide'),grid:rect('.zb-feed-grid'),calendar:rect('.zb-feed-grid>.zb-calendar'),events:rect('.zb-feed-grid>.zb-news-panel'),days:[...document.querySelectorAll('.zb-news-day')].map(e=>({top:e.getBoundingClientRect().top,left:e.getBoundingClientRect().left}))};});
   assert.ok(layout.news.bottom<layout.grid.top);
   assert.ok(Math.abs(layout.news.width-layout.grid.width)<1);
   if(width===1400){assert.equal(layout.calendar.top,layout.events.top);assert.ok(layout.calendar.left<layout.events.left);assert.equal(layout.days[0].top,layout.days[2].top);assert.ok(layout.days[0].left<layout.days[1].left&&layout.days[1].left<layout.days[2].left);}
   if(width===1000){assert.equal(layout.days[0].top,layout.days[1].top);assert.ok(layout.days[2].top>layout.days[0].top);}
   if(width===320){assert.ok(layout.days[0].top<layout.days[1].top&&layout.days[1].top<layout.days[2].top);}
   const today=page.locator('.zb-news-day').first();
   assert.match(await today.textContent(),/Balancing, Fixes and Changes[\s\S]*Maintenance completed/);
   assert.equal(await today.locator('li').first().isVisible(),false);
   assert.equal(await today.locator('summary').innerText(),'News Ticker (2)');
   assert.equal(await today.locator('a.zb-news').isVisible(),true);
   await today.locator('.zb-news-ticker summary').click();
   assert.equal(await today.locator('li').first().isVisible(),true);
   const tickerOnly=page.locator('.zb-news-day').nth(1);
   assert.equal(await tickerOnly.locator('.zb-news').count(),0);
   await tickerOnly.locator('summary').click();
   assert.equal(await tickerOnly.locator('li').isVisible(),true);
   await tickerOnly.locator('summary').click();
   assert.equal(await today.locator('a.zb-news').getAttribute('href'),'https://www.tibia.com/news/?subtopic=newsarchive&id=9024');
   const img=today.locator('img');
   await img.dispatchEvent('error');
   assert.equal(await img.isVisible(),false);
   assert.equal(await today.locator('.zb-news-fallback').isVisible(),true);
   await page.evaluate(d=>zbRender(d),data);
   assert.equal(await page.locator('.zb-news-ticker').first().evaluate(e=>e.open),true,'Expansão do dia é preservada ao atualizar');
   await today.locator('.zb-news-ticker summary').click();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   if(process.env.NEWS_SCREENSHOT_DIR&&width!==1000){await page.locator('.zb-news-wide').scrollIntoViewIfNeeded();await page.screenshot({path:process.env.NEWS_SCREENSHOT_DIR+`/news-home-reorganizada-${width===1400?'wide':'compact'}.png`});}
  }
  for(const [estado,velho,expected] of [['desatualizado',true,'consulta anterior'],['indisponivel',false,'indisponível'],['selecionar_mundo',false,'Escolha um mundo']]){
   await page.evaluate(d=>zbRender(d),{...data,killstatistics:{...data.killstatistics,estado,velho}});
   await page.locator('.zb-kills').evaluate(e=>e.open=true);
   assert.match(await page.locator('.zb-kills').innerText(),new RegExp(expected));
  }
  data.killstatistics.bosses[0].nome='<img src=x onerror="window.pwned=1">';
  data.killstatistics.mundo='Xybra" onclick="x';
  await page.evaluate(d=>zbRender(d),data);
  assert.equal(await page.locator('.zb-kills img').count(),0);
  assert.equal(await page.locator('.zb-kills a').count(),0);
  data.noticias=[{id:'9024" onclick="window.pwned=1',titulo:'<img src=x onerror="window.pwned=1">',data:'2026-10-20',imagem:'https://evil.example/x.png'}];
  data.news_ticker=[{id:-1,data:'2026-10-20',texto:'<script>window.pwned=1</script>'}];
  data.noticias_velhas=true;data.news_ticker_velho=true;
  await page.evaluate(d=>zbRender(d),data);
  assert.equal(await page.locator('.zb-news-panel').first().locator('img, a, script').count(),0);
  assert.match(await page.locator('.zb-news-panel').first().innerText(),/Dados anteriores/);
  assert.match(await page.locator('.zb-news-panel').first().innerText(),/News Ticker:.*dados anteriores/);
  assert.equal(await page.evaluate(()=>window.pwned),undefined);
  await page.evaluate(d=>zbRender(d),{...data,noticias:[],news_ticker:[],anuncios:[]});
  assert.match(await page.locator('#zb-result').innerText(),/Nenhuma notícia disponível/);
  assert.match(await page.locator('#zb-result').innerText(),/Nenhum anúncio disponível/);
  assert.deepEqual(errors,[]);
  console.log('ZandaoBot: Kill Statistics and News/events, daily ticker grouping, safe links/images, fallback states, escaped input and 1400/320px layout OK');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
