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
  const data={mundo:'Xybra',dia:'2026-10-15',consulta:'2026-10-15T15:00:00Z',dream_court:{nome:'Maxxenius'},killstatistics:{estado:'disponivel',mundo:'Xybra',consulta:1792076400,processamento:'2026-10-15T14:03:02Z',bosses:bosses.map((nome,i)=>({nome,last_day_killed:i===2?null:i,last_week_killed:i+10}))}};
  for(const width of [1400,320]){
   await page.setViewportSize({width,height:1000});
   await page.evaluate(d=>zbRender(d),data);
   await page.locator('.zb-kills').evaluate(e=>e.open=true);
   assert.equal(await page.locator('.zb-kills tbody tr').count(),5);
   assert.equal(await page.locator('.zb-kills tbody tr').nth(0).locator('td').first().innerText(),'0');
   assert.equal(await page.locator('.zb-kills tbody tr').nth(2).locator('td').first().innerText(),'—');
   assert.match(await page.locator('.zb-kills').innerText(),/Processamento no TibiaData/);
   assert.match(await page.locator('.zb-kills').innerText(),/não confirma o boss atual/);
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
  assert.deepEqual(errors,[]);
  console.log('ZandaoBot Kill Statistics: five counts, missing vs zero, source times, fallback states, escaped input and 1400/320px layout OK');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
