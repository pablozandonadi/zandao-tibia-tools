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
   noticias:[{id:9024,titulo:'Balancing, Fixes and Changes',data:'2026-10-20',categoria:'development',imagem:'https://static.tibia.com/images/news/news_fixes_243x200.png'}],
   anuncios:[{id:9001,titulo:'Orcsoberfest',data:'2026-10-07',categoria:'community'}],
   news_ticker:[{id:9025,data:'2026-10-20',texto:'Maintenance completed.'},{id:9027,data:'2026-10-20',texto:'Second notice.'},{id:9026,data:'2026-10-19',texto:'Only a ticker today.'}]};
  for(const width of [1400,320]){
   await page.setViewportSize({width,height:1000});
   await page.evaluate(d=>zbRender(d),data);
   await page.locator('.zb-kills').evaluate(e=>e.open=true);
   assert.equal(await page.locator('.zb-kills tbody tr').count(),5);
   assert.equal(await page.locator('.zb-kills tbody tr').nth(0).locator('td').first().innerText(),'0');
   assert.equal(await page.locator('.zb-kills tbody tr').nth(2).locator('td').first().innerText(),'—');
   assert.match(await page.locator('.zb-kills').innerText(),/Processamento no TibiaData/);
   assert.match(await page.locator('.zb-kills').innerText(),/não confirma o boss atual/);
   assert.deepEqual(await page.locator('.zb-feed-stack h2').allTextContents(),['News','Eventos do Tibia']);
   assert.deepEqual(await page.locator('.zb-news-day h3').allTextContents(),['20/10/2026','19/10/2026']);
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
   const cards=await page.locator('.zb-feed-stack>.zb-panel').evaluateAll(es=>es.map(e=>e.getBoundingClientRect().top));
   assert.ok(cards[0]<cards[1]);
   await today.locator('.zb-news-ticker summary').click();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
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
  assert.match(await page.locator('.zb-feed-stack').innerText(),/Nenhuma notícia disponível/);
  assert.match(await page.locator('.zb-feed-stack').innerText(),/Nenhum anúncio disponível/);
  assert.deepEqual(errors,[]);
  console.log('ZandaoBot: Kill Statistics and News/events, daily ticker grouping, safe links/images, fallback states, escaped input and 1400/320px layout OK');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
