const assert=require('node:assert/strict');
const inputs={};
for(const key of ['gold','gold_por_tc','tc_pacote','reais_pacote','automatico','atualizar','salvar','feedback','resultado','cotacao']){
 inputs['conversao-'+key]={value:'',checked:true,textContent:'',disabled:false,events:{},addEventListener(name,fn){this.events[name]=fn;}};
}
inputs['assistente-world']={value:'Antica'};
global.document={getElementById(id){return inputs[id]||null;}};
const calculations=[],requests=[],saves=[];
global.window={addEventListener(){},pywebview:{api:{
 async conversao_tc_carregar(){return {valores:{gold_por_tc:'46600',tc_pacote:'250',reais_pacote:'50'},automatico:true};},
 async conversao_tc_calcular(gold,values){calculations.push({...values});return {tc:'20.00',reais:'4.00'};},
 conversao_tc_cotacao(world,force){return new Promise(resolve=>requests.push({world,force,resolve}));},
 async conversao_tc_salvar(values,automatic){saves.push({values,automatic});return {message:'Salvo'};}
}}};
const ui=require('./web/assistente.js');
const input=key=>inputs['conversao-'+key];
const wait=()=>new Promise(resolve=>setTimeout(resolve,220));
const quote=(world,price)=>({estado:'ok',mundo:world,gold_por_tc:price,data_base:new Date().toISOString(),consulta:new Date().toISOString()});
(async()=>{
 await ui.bootConversion();input('gold').value='1kk';input('gold').events.input();await wait();
 assert.equal(calculations.at(-1).gold_por_tc,'46600');
 const old=ui.refreshQuote();assert.equal(requests.length,1);
 await ui.refreshQuote(true);assert.equal(requests.length,1,'consulta em voo não duplica nem ao atualizar');
 inputs['assistente-world'].value='Honbra';ui.manualQuote('Mundo alterado. Valor manual em uso.');
 const current=ui.refreshQuote();requests[1].resolve(quote('Honbra',55000));await current;await wait();
 assert.equal(calculations.at(-1).gold_por_tc,'55000');
 assert.equal(calculations.at(-1).reais_pacote,'50');assert.equal(calculations.at(-1).tc_pacote,'250');
 requests[0].resolve(quote('Antica',46000));await old;await wait();
 assert.match(input('cotacao').textContent,/Honbra/);assert.equal(calculations.at(-1).gold_por_tc,'55000');
 await ui.refreshQuote();assert.equal(requests.length,2,'refresh periódico reutiliza cotação');
 const pending=ui.refreshQuote(true);input('automatico').checked=false;input('automatico').events.change();
 requests[2].resolve(quote('Honbra',99999));await pending;await wait();
 assert.match(input('cotacao').textContent,/manual/);assert.equal(calculations.at(-1).gold_por_tc,'46600');
 await input('salvar').events.click();
 assert.deepEqual(saves[0],{values:{gold_por_tc:'46600',tc_pacote:'250',reais_pacote:'50'},automatic:false});
 input('automatico').checked=true;const stale=ui.refreshQuote(true);
 requests[3].resolve({...quote('Honbra',60000),estado:'antiga',data_base:new Date(Date.now()-37*3600000).toISOString(),motivo:'Cotação antiga: o TibiaTrade ainda não atualizou este mundo.'});
 await stale;await wait();assert.equal(calculations.at(-1).gold_por_tc,'60000','cotação antiga é usada, com aviso');
 assert.match(input('cotacao').textContent,/⚠ Cotação antiga/);
 input('gold_por_tc').value='50k';input('gold_por_tc').events.input();await wait();
 assert.equal(input('automatico').checked,false);assert.equal(calculations.at(-1).gold_por_tc,'50k');
 const realNow=Date.now;let offset=0;Date.now=()=>realNow()+offset;
 try{
  input('automatico').checked=true;const unavailable=ui.refreshQuote(true);
  requests[4].resolve({estado:'indisponivel',mundo:'Honbra',motivo:'Cotação indisponível. Valor manual em uso.'});await unavailable;
  await ui.refreshQuote();assert.equal(requests.length,5);
  offset=59000;await ui.refreshQuote();assert.equal(requests.length,5,'falha respeita cooldown de 60 segundos');
  offset=61000;const retry=ui.refreshQuote();assert.equal(requests.length,6,'falha permite recuperação automática depois de 60 segundos');
  requests[5].resolve(quote('Honbra',51000));await retry;await wait();
  assert.equal(calculations.at(-1).gold_por_tc,'51000');
 }finally{Date.now=realNow;}
 console.log('Market cotação UI: troca de mundo, desativação durante consulta, persistência manual, reais preservados e cotação antiga passaram.');
})().catch(error=>{console.error(error);process.exitCode=1;});
