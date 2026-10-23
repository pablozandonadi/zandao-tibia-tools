(function(){
'use strict';
const el=id=>document.getElementById(id);
const fields={
 duration_seconds:['Duração em segundos','number'],label:['Nome','text'],personal:['Associar ao personagem','checkbox'],timer_id:['Timer','timer'],delta_seconds:['Adicionar segundos','number'],
 reference_level:['Meu level (consulta hipotética)','number'],party_levels:['Levels da party, separados por vírgula','text'],include_active:['Incluir level cadastrado','checkbox'],
 boss_id:['Boss','boss'],boosted:['Confirmo: Archfoe boosted do dia e elegível (informado por mim): 3 de progresso / 1 abate real','checkbox'],killed_at:['Horário do abate (vazio = agora)','datetime-local'],corrected_at:['Horário corrigido','datetime-local'],total_kills:['Total de progresso Bosstiary','number'],delta_kills:['Adicionar progresso','number'],bosses:['Catálogo JSON com fonte, categoria, cooldown e verificação','textarea'],
 stamina_minutes:['Stamina em minutos (38h = 2280)','number'],logged_out_at:['Logout (vazio = agora)','datetime-local'],logged_in_at:['Login (vazio = agora)','datetime-local'],reference_at:['Referência (vazio = agora)','datetime-local'],target_datetime:['Projetar para (vazio = agora)','datetime-local'],target_stamina_minutes:['Meta em minutos (39h = 2340; 42h = 2520)','number'],starting_stamina_minutes:['Stamina inicial em minutos','number'],desired_stamina_minutes:['Meta desejada em minutos','number'],desired_at:['Alcançar a meta em','datetime-local'],
 item:['Item','text'],price:['Preço GP, K ou KK (ex.: 35k, 1.5kk)','text'],offer_type:['Tipo de oferta','offer'],observed_at:['Data observada (vazio = agora)','datetime-local'],days:['Período em dias (7, 30, 90)','number'],observation_id:['ID do registro (vazio = último do item/tipo)','text'],reason:['Motivo da correção ou exclusão','text'],direction:['Limite','direction']
};
const operations={
 timers:[['timer.create','Criar timer',['duration_seconds','label','personal']],['timer.list','Listar ativos e histórico',[]],['timer.get','Consultar timer',['timer_id']],['timer.extend','Estender timer',['timer_id','delta_seconds']],['timer.edit','Editar timer',['timer_id','label','duration_seconds']],['timer.cancel','Cancelar timer',['timer_id']],['timer.repeat','Repetir timer do histórico',['timer_id']]],
 shared:[['shared.range','Consultar faixa',['reference_level']],['shared.check','Verificar party',['party_levels','include_active']],['shared.party_range','Faixa de inclusão na party',['party_levels']]],
 bosses:[['boss.kill','Registrar abate + Bosstiary',['boss_id','killed_at','boosted']],['boss.cooldown.list','Cooldowns e Bosstiary do personagem',[]],['bosstiary.get','Consultar progresso',['boss_id']],['bosstiary.set_total','Definir total (substitui)',['boss_id','total_kills']],['bosstiary.increment','Adicionar progresso',['boss_id','delta_kills']],['boss.kill.undo','Desfazer último abate',['boss_id']],['boss.kill.correct_time','Corrigir horário do último abate',['boss_id','corrected_at']],['boss.alert','Avisar quando liberar',['boss_id']],['boss.catalog.import','Importar catálogo validado',['bosses']]],
 stamina:[['stamina.logout','Registrar logout',['stamina_minutes','logged_out_at']],['stamina.project','Projetar recuperação',['target_datetime']],['stamina.time_to','Quando alcanço a meta?',['target_stamina_minutes']],['stamina.reverse','Último horário para deslogar',['starting_stamina_minutes','desired_stamina_minutes','desired_at']],['stamina.login','Registrar login',['logged_in_at']],['stamina.correct','Corrigir referência',['stamina_minutes','reference_at']],['stamina.alert','Avisar ao alcançar meta',['target_stamina_minutes']],['stamina.get','Ver referência declarada',[]]],
 market:[['market.price.add','Registrar preço informado por você',['item','price','offer_type','observed_at']],['market.stats','Histórico e comparação (não grava)',['item','offer_type','days','price']],['market.item.watch','Adicionar item monitorado',['item']],['market.watch.list','Itens monitorados',[]],['market.price.correct','Corrigir observação',['item','offer_type','observation_id','price','reason']],['market.price.delete','Excluir observação',['item','offer_type','observation_id','reason']],['market.alert.create','Alerta para novos preços informados',['item','offer_type','direction','price']],['market.alert.list','Ver alertas',[]]]
};
const integerFields=new Set(['duration_seconds','delta_seconds','reference_level','total_kills','delta_kills','stamina_minutes','target_stamina_minutes','starting_stamina_minutes','desired_stamina_minutes','days']);
function payload(intent,values){
 const result={};
 for(const [key,value] of Object.entries(values)){
  if(value===''||value===undefined)continue;
  if(integerFields.has(key)){const n=Number(value);if(!Number.isSafeInteger(n))throw new Error('Informe números inteiros.');result[key]=n;}
  else if(key==='party_levels'){result[key]=value.split(/[,;\s]+/).filter(Boolean).map(Number);if(!result[key].length||result[key].some(n=>!Number.isSafeInteger(n)||n<1))throw new Error('Informe levels inteiros separados por vírgulas.');}
  else if(key==='bosses')result[key]=JSON.parse(value);
  else if(fields[key]&&fields[key][1]==='datetime-local'){const date=new Date(value);if(!Number.isFinite(date.getTime()))throw new Error('Data inválida.');result[key]=date.toISOString();}
  else result[key]=value;
 }
 return result;
}
async function execute(api,intent,args,context,id){return api.assistente_executar(intent,args,{...context},id);}
let state={context:{},timers:[],catalog:{bosses:[]},history:[]},booted=false,busy=false,active='overview';
function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function button(text,fn){const n=node('button',text,'btn btn-sm');n.type='button';n.addEventListener('click',fn);return n;}
function stamp(v){return v?new Date(v).toLocaleString('pt-BR'):'Não informado';}
function decimalBR(value){const [whole,fraction]=String(value).split('.');return whole.replace(/\B(?=(\d{3})+(?!\d))/g,'.')+(fraction?','+fraction:'');}
const conversionKeys=['gold_por_tc','tc_pacote','reais_pacote'];
function conversionValues(){return Object.fromEntries(conversionKeys.map(key=>[key,el('conversao-'+key).value.trim()]));}
let conversionRevision=0,conversionTimer,quoteRevision=0,quoteWorld='',quoteAt=0,quoteValue=null,quoteExpires=0,quoteInterval=3600000,quotePending=0,quoteStale=false,conversionReady=false;
function manualQuote(text='Valor manual em uso.'){
 ++quoteRevision;quoteValue=null;quoteWorld='';quoteAt=0;el('conversao-cotacao').textContent=text;conversionInput();
}
async function refreshQuote(force=false){
 if(!conversionReady)return;
 const world=el('assistente-world').value.trim(),automatic=el('conversao-automatico').checked;
 if(!automatic)return;
 if(!world){manualQuote('Selecione o mundo dos preços abaixo. Valor manual em uso.');return;}
 if(world===quoteWorld&&quotePending===quoteRevision)return;
 if(!force&&world===quoteWorld&&Date.now()-quoteAt<quoteInterval&&(quoteValue===null||Date.now()<=quoteExpires))return;
 const revision=++quoteRevision;quotePending=revision;quoteWorld=world;quoteAt=Date.now();quoteValue=null;quoteInterval=3600000;
 el('conversao-cotacao').textContent=`Consultando ${world}… Valor manual em uso.`;conversionInput();
 try{
  const data=await window.pywebview.api.conversao_tc_cotacao(world,force||quoteStale);
  if(revision!==quoteRevision||!el('conversao-automatico').checked||world!==el('assistente-world').value.trim())return;
  if(data.registrado)refreshPrices(true);  // cotação nova entrou no histórico do Tibia Coin
  if(data.estado==='indisponivel')quoteInterval=60000;
  quoteStale=data.estado==='antiga';
  const age=Date.now()-new Date(data.data_base).getTime();
  if((data.estado==='ok'||data.estado==='antiga')&&data.mundo.toLowerCase()===world.toLowerCase()&&Number.isSafeInteger(data.gold_por_tc)&&data.gold_por_tc>0&&data.gold_por_tc<=1e12&&age>=-300000){
   quoteValue=data.gold_por_tc;quoteExpires=Infinity;
   if(data.estado==='antiga')quoteInterval=900000;  // tenta de novo em 15 min: o site pode ter atualizado
   if(!el('conversao-gold_por_tc').value.trim())el('conversao-gold_por_tc').value=String(quoteValue);  // reserva para quando o site cair
  }
  const info=`${world} · ${quoteValue?decimalBR(quoteValue)+' GP/TC · média diária de venda'+(data.estado==='antiga'?' · ⚠ '+data.motivo:''):data.motivo||'Cotação inválida. Valor manual em uso.'}`;
  el('conversao-cotacao').textContent=info+(data.data_base?` · Base: ${stamp(data.data_base)}`:'')+(data.consulta?` · Consulta: ${stamp(data.consulta)}`:'');
  if(!quoteValue&&!el('conversao-cotacao').textContent.includes('manual'))el('conversao-cotacao').textContent+=' · Valor manual em uso.';
 }catch(e){if(revision!==quoteRevision)return;quoteInterval=60000;el('conversao-cotacao').textContent='Cotação indisponível. Valor manual em uso.';}
 if(quotePending===revision)quotePending=0;
 conversionInput();
}
function conversionInput(){
 const revision=++conversionRevision,out=el('conversao-resultado');clearTimeout(conversionTimer);out.textContent='Informe o gold obtido.';
 if(!el('conversao-gold').value.trim())return;
 const values=conversionValues(),gold=el('conversao-gold').value.trim();
 if(quoteValue!==null&&Date.now()>quoteExpires){++quoteRevision;quoteValue=null;quoteWorld='';el('conversao-cotacao').textContent='Cotação com mais de 36 horas. Valor manual em uso.';}
 if(el('conversao-automatico').checked&&quoteWorld===el('assistente-world').value.trim()&&quoteValue!==null)values.gold_por_tc=String(quoteValue);
 if([gold,...Object.values(values)].some(value=>!value||value.length>48||!/^\d[\d.,]*(?:\s*(?:k|kk|gp|gold))?$/i.test(value))){out.textContent='Confira os valores informados.';return;}
 out.textContent='Calculando…';conversionTimer=setTimeout(async()=>{
  try{const result=await window.pywebview.api.conversao_tc_calcular(gold,values);if(revision!==conversionRevision)return;out.textContent=result.erro||`≈ ${decimalBR(result.tc)} TC · ≈ R$ ${decimalBR(result.reais)}`;}
  catch(e){if(revision===conversionRevision)out.textContent='Não foi possível calcular agora.';}
 },180);
}
async function bootConversion(){
 for(const key of ['gold',...conversionKeys])el('conversao-'+key).addEventListener('input',()=>{if(key==='gold_por_tc'){el('conversao-automatico').checked=false;manualQuote();}else conversionInput();});
 el('conversao-automatico').addEventListener('change',()=>{manualQuote();refreshQuote();});
 el('conversao-atualizar').addEventListener('click',()=>refreshQuote(true));
 const save=el('conversao-salvar'),feedback=el('conversao-feedback');
 save.addEventListener('click',async()=>{save.disabled=true;feedback.textContent='Salvando…';try{const result=await window.pywebview.api.conversao_tc_salvar(conversionValues(),el('conversao-automatico').checked,el('assistente-world').value.trim());feedback.textContent=result.erro||result.message+(result.registrado?' Valor manual registrado no histórico do Tibia Coin.':'');if(result.registrado)refreshPrices(true);}catch(e){feedback.textContent='Não foi possível salvar agora.';}finally{save.disabled=false;}});
 try{const data=await window.pywebview.api.conversao_tc_carregar();for(const key of conversionKeys)el('conversao-'+key).value=String(data.valores[key]).replace('.',',');el('conversao-automatico').checked=data.automatico!==false;feedback.textContent=data.aviso||'';}
 catch(e){feedback.textContent='Não foi possível carregar a conversão salva. Valores padrão em uso.';}
 finally{for(const key of conversionKeys)el('conversao-'+key).disabled=false;el('conversao-automatico').disabled=false;el('conversao-atualizar').disabled=false;save.disabled=false;conversionReady=true;conversionInput();if(active==='market')refreshQuote();}
}
let pricesRevision=0,pricesKey='',pricesTimer;
async function refreshPrices(force=false){
 const world=el('assistente-world').value.trim(),key=JSON.stringify([world,state.revision]);
 if(!force&&pricesKey===key)return;pricesKey=key;const revision=++pricesRevision,out=el('assistente-precos');if(!out.children.length)out.append(node('p',world?'Carregando preços…':'Informe o mundo para consultar seus preços.'));
 if(!world)return;
 try{const data=await window.pywebview.api.assistente_precos(world);if(revision!==pricesRevision||el('assistente-world').value.trim()!==world)return;if(data.erro)throw new Error(data.erro);
  if(window.assistenteFerramentas)await window.assistenteFerramentas.prices(data);
 }catch(e){if(revision===pricesRevision){pricesKey='';out.replaceChildren(node('p',e.message||'Não foi possível carregar seus preços.'));}}
}
function table(rows,columns){const t=node('table',undefined,'assistente-table');const head=node('tr');for(const [,title] of columns)head.append(node('th',title));t.append(head);for(const row of rows){const tr=node('tr');for(const [key] of columns)tr.append(node('td',row[key]===null||row[key]===undefined?'—':String(row[key])));t.append(tr);}return t;}
function showResult(module,data){
 const out=el('assistente-result-'+module);out.replaceChildren();out.append(node('p',data.message||data.note||'Consulta concluída.'));
 if(data.range)out.append(node('strong',`Faixa: ${data.range[0]} a ${data.range[1]}${data.compatible===undefined?'':data.compatible?' · Compatível por level':' · Incompatível por level'}`));
 if(data.source)out.append(node('p',data.source,'dica'));

 if(data.boss||data.bosses){const rows=(data.bosses||[data.boss]).map(b=>({...b,last:stamp(b.last_killed_at),ready:b.available_at?stamp(b.available_at):'Cooldown não verificado',goal:b.complete?'Completo':b.next_goal?`${b.progress} / ${b.next_goal} · faltam ${b.missing}`:'Meta não verificada'}));out.append(table(rows,[['name','Boss'],['real_kills','Abates reais'],['goal','Bosstiary'],['last','Último abate'],['ready','Disponibilidade']]));}
 if(data.stamina)out.append(node('p',`${data.stamina.stamina_minutes} min · ${data.stamina.offline?'Offline declarado':'Online declarado'} · Referência: ${stamp(data.stamina.reference_at)}`));
 if(data.at)out.append(node('strong',stamp(data.at)));
 if(data.stamina_minutes!==undefined)out.append(node('strong',`${Math.floor(data.stamina_minutes/60)}h${String(data.stamina_minutes%60).padStart(2,'0')}`));
 if(data.count!==undefined){out.append(node('p',`${data.count} amostras · mediana ${data.median??'—'} GP · média ${data.mean??'—'} GP · mínimo ${data.minimum??'—'} · máximo ${data.maximum??'—'} · amplitude ${data.spread??'—'} · variação ${data.variation_percent??'—'}% · idade ${data.age_seconds===null?'—':Math.floor(data.age_seconds/3600)+'h'}`));out.append(node('p',`${data.insufficient?'Amostra insuficiente para avaliar barato/caro. ':''}${data.comparison||''} Preços informados por você; sem cotação em tempo real.`));const rows=data.observations.map(p=>({...p,date:stamp(p.at)}));out.append(table(rows,[['id','ID para correção'],['date','Data'],['price_gp','GP'],['offer_type','Oferta']]));chart(out,rows);}
 if(data.observation)out.append(node('p',`ID: ${data.observation.id} · ${data.observation.item} · ${data.observation.price_gp} GP · ${stamp(data.observation.at)}`));
 if(data.items)out.append(node('p',data.items.join(', ')));
 if(data.alerts)out.append(table(data.alerts,[['item','Item'],['threshold','Limite GP'],['direction','Direção'],['fired','Já avisado']]));
}
function chart(out,rows,title='Evolução dos preços informados no período selecionado'){if(rows.length<2)return;const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 600 150');svg.setAttribute('role','img');svg.setAttribute('aria-label',title);const values=rows.map(r=>r.price_gp),low=Math.min(...values),high=Math.max(...values);const line=document.createElementNS(ns,'polyline');line.setAttribute('points',values.map((v,i)=>`${10+i*580/(values.length-1)},${140-(v-low)*130/(high-low||1)}`).join(' '));line.setAttribute('fill','none');line.setAttribute('stroke','currentColor');line.setAttribute('stroke-width','3');svg.append(line);out.append(svg);}
function renderFields(module,initial={}){
 const intent=el('assistente-op-'+module).value;const keys=operations[module].find(op=>op[0]===intent)[2],container=el('assistente-fields-'+module);container.replaceChildren();
 for(const key of keys){const [caption,type]=fields[key],wrap=node('label',caption);let input;if(['boss','timer','offer','direction'].includes(type)){input=node('select');let options=type==='boss'?state.catalog.bosses.map(b=>[b.boss_id,b.name]):type==='timer'?state.timers.map(t=>[t.id,`${t.label} (${t.status})`]):type==='offer'?[['sell','Venda'],['buy','Compra'],['traded','Negociado']]:[['below','Abaixo de'],['above','Acima de']];for(const [v,title] of options){const option=node('option',title);option.value=v;input.append(option);}}else{input=node(type==='textarea'?'textarea':'input');if(type!=='textarea')input.type=type;}
 input.id=`assistente-${module}-${key}`;input.name=key;input.maxLength=key==='bosses'?30000:120;if(type==='number'){input.step='1';input.min='0';}if(type==='checkbox')input.checked=initial[key]===true;else if(initial[key]!==undefined)input.value=initial[key];else if(key==='days')input.value='30';else if(key==='item')input.value='Tibia Coin';else if(key==='duration_seconds')input.value='30';else if(key==='target_stamina_minutes'||key==='desired_stamina_minutes')input.value='2520';else if(key==='stamina_minutes'||key==='starting_stamina_minutes')input.value='2280';wrap.htmlFor=input.id;wrap.append(input);container.append(wrap);}
}
async function run(module,intent,args){
 if(busy)return;busy=true;const status=el('assistente-feedback');status.textContent='Processando…';
 const context={...state.context},id=crypto.randomUUID();
 if(module==='market'&&el('assistente-world').value.trim())context.world_id=el('assistente-world').value.trim();
 try{const data=await execute(window.pywebview.api,intent,args,context,id);if(data.erro)throw new Error(data.erro);if(JSON.stringify(context)!==JSON.stringify({...state.context,...(module==='market'?{world_id:el('assistente-world').value.trim()}: {})}))return false;showResult(module,data);status.textContent=data.message||'Concluído.';await refresh();return true;}
 catch(e){status.textContent=e.message||'Não foi possível concluir.';return false;}finally{busy=false;}
}
let refreshVersion=0;
async function refresh(){
 if(!window.pywebview||!window.pywebview.api)return;
 const version=++refreshVersion;
 try{const data=await window.pywebview.api.assistente_estado();if(version!==refreshVersion)return;if(data.erro)throw new Error(data.erro);state=data;
 if(window.chatEstado)window.chatEstado(data);
 for(const input of document.querySelectorAll('select[name=timer_id],select[name=boss_id]')){const previous=input.value;const rows=input.name==='timer_id'?data.timers.map(t=>[t.id,`${t.label} (${t.status})`]):data.catalog.bosses.map(b=>[b.boss_id,b.name]);const sig=rows.join('\n');if(input.dataset.sig===sig)continue;input.dataset.sig=sig;input.replaceChildren();for(const [value,title] of rows){const option=node('option',title);option.value=value;input.append(option);}if(rows.some(r=>r[0]===previous))input.value=previous;}
 if(!el('assistente-world').value)el('assistente-world').value=data.context.world_id||'';
 el('assistente-context').textContent=`Personagem: ${data.context.character_id||'Selecione em Meus personagens'} · Level: ${data.context.level||'—'} · Mundo: ${data.context.world_id||'Não informado'}`;el('assistente-overview').textContent=`${data.timers.filter(t=>t.status==='active').length} timers ativos · Bosses e stamina por personagem · Market privado por mundo. Alertas funcionam enquanto o aplicativo está aberto e são reconciliados uma vez ao reabrir.`;if(window.assistenteFerramentas)window.assistenteFerramentas.update(data);
 const names=el('bosstiary-nomes');if(names&&names.children.length!==data.catalog.bosses.length)names.replaceChildren(...data.catalog.bosses.map(b=>{const o=node('option');o.value=b.name;return o;}));
 const key=`${data.context.character_id}|${data.revision}`;if(['bosstiary','bosses'].includes(active)&&key!==bosstiaryKey){bosstiaryKey=key;await loadBosstiary();}
 if(active==='stamina')await renderStamina();if(active==='market'){await refreshPrices();refreshQuote();}}
 catch(e){if(version===refreshVersion)el('assistente-feedback').textContent=e.message;}
}
// Bosstiary: lista do personagem em uso, no estilo da Cyclopedia do Tibia.
const STAR_NAMES=['Prowess','Expertise','Mastery'];let bosstiaryRows=[],bosstiaryKey='',bossLoadVersion=0;
const bossImage=name=>`assets/creatures/${name.split(' (')[0].toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_|_$/g,'')}.gif`;
async function loadBosstiary(){
 const version=++bossLoadVersion,context={...state.context};
 const out=el('bosstiary-lista');
 if(!state.context.character_id){bosstiaryRows=[];renderCooldowns();out.replaceChildren(node('p','Selecione um personagem em Meus personagens.','dica'));return;}
 const data=await window.pywebview.api.assistente_executar('boss.cooldown.list',{},context);
 if(version!==bossLoadVersion||JSON.stringify(context)!==JSON.stringify(state.context))return;
 if(data.erro){out.replaceChildren(node('p',data.erro,'dica'));return;}
 bosstiaryRows=data.bosses;renderBosstiary();renderCooldowns();
}
// Boss Cooldowns: igual ao widget do Tibia (imagem, nome, tempo em vermelho; o que libera primeiro em cima).
function span(ms){const m=Math.max(1,Math.ceil(ms/60000)),d=Math.floor(m/1440),h=Math.floor(m/60)%24;return d?`${d}d ${h}h`:h?`${h}h ${m%60}min`:`${m%60}min`;}
const noImage=new Set();
function bossPicture(name){
 const src=bossImage(name);if(noImage.has(src))return node('span','?','bosstiary-sombra');
 const img=node('img');img.alt='';img.loading='lazy';img.src=src;img.addEventListener('error',()=>{noImage.add(src);img.replaceWith(node('span','?','bosstiary-sombra'));});return img;
}
function cooldownForm(b){
 const form=node('form',undefined,'cooldowns-informar'),hours=node('input');hours.type='number';hours.min='1';hours.max='8760';hours.step='1';hours.required=true;hours.placeholder='horas';hours.setAttribute('aria-label',`Cooldown de ${b.name} em horas`);
 form.append(hours,node('button','Salvar','btn btn-sm'));form.addEventListener('submit',e=>{e.preventDefault();quickRun('boss.cooldown.set',{boss_id:b.boss_id,cooldown_minutes:Number(hours.value)*60});});return form;
}
function renderCooldowns(){
 const list=el('cooldowns-lista'),q=el('cooldowns-busca').value.trim().toLowerCase(),now=Date.now();
 const order=({b,left})=>left>0?left:b.cooldown_minutes?1e15:2e15;
 const rows=bosstiaryRows.filter(b=>!q||[b.name,...b.aliases].some(n=>n.toLowerCase().includes(q)))
  .map(b=>({b,left:b.available_at?new Date(b.available_at)-now:0}))
  .sort((x,y)=>order(x)-order(y)||x.b.name.localeCompare(y.b.name));
 list.replaceChildren(...rows.map(({b,left})=>{
  const li=node('li');li.append(bossPicture(b.name),node('strong',b.name));
  if(left>0){const t=node('span',span(left),'cooldowns-tempo');t.dataset.until=b.available_at;li.append(t);}
  else if(b.cooldown_minutes)li.append(node('span','Disponível','cooldowns-livre'));
  else li.append(button('Informar cooldown',e=>{const form=cooldownForm(b);e.currentTarget.replaceWith(form);form.querySelector('input').focus();}));
  return li;}));
 if(!rows.length)list.append(node('li','Nenhum boss encontrado.','dica'));
}
// A cada 20 s só os tempos mudam; a lista inteira não é redesenhada.
function tickCooldowns(){for(const t of document.querySelectorAll('#cooldowns-lista [data-until]')){const left=new Date(t.dataset.until)-Date.now();if(left>0)t.textContent=span(left);else{t.className='cooldowns-livre';t.textContent='Disponível';delete t.dataset.until;}}}
function bossCard(b){
 const card=node('article',undefined,'card calmo bosstiary-card'),goals=b.goals||[],stars=goals.filter(g=>b.progress>=g).length;
 const img=bossPicture(b.name);
 const bar=node('progress');bar.max=b.next_goal||goals.at(-1)||1;bar.value=Math.min(b.progress,bar.max);bar.setAttribute('aria-label',`Progresso de ${b.name}`);
 const goal=!goals.length?'Fora do Bosstiary':b.next_goal?`faltam ${b.missing} para ${STAR_NAMES[stars]}`:'Mastery completo';
 card.append(node('strong',b.name),img,node('p',`Total kills: ${b.progress}`),bar,node('span',goals.length?'★'.repeat(stars)+'☆'.repeat(3-stars):'','bosstiary-estrelas'),node('p',goal,'dica'));
 card.append(button('+1 kill',()=>quickRun('boss.kill',{boss_id:b.boss_id})),button('Editar total',()=>{el('bosstiary-boss').value=b.name;el('bosstiary-total').value=b.progress;el('bosstiary-total').focus();}));
 return card;
}
function renderBosstiary(){
 const onlyKilled=el('bosstiary-com-kills').checked,q=el('bosstiary-busca').value.trim().toLowerCase();
 const cats=new Set([...document.querySelectorAll('[data-bosstiary-cat]:checked')].map(i=>i.dataset.bosstiaryCat));
 const rows=bosstiaryRows.filter(b=>(!onlyKilled||b.progress>0)&&cats.has(b.category)&&(!q||[b.name,...b.aliases].some(n=>n.toLowerCase().includes(q)))).sort((x,y)=>y.progress-x.progress||x.name.localeCompare(y.name));
 const killed=bosstiaryRows.filter(b=>b.progress>0).length;
 el('bosstiary-lista').replaceChildren(...rows.map(bossCard));
 el('bosstiary-resumo').textContent=`${killed} bosses com kills neste personagem · mostrando ${rows.length} de ${bosstiaryRows.length}`;
 if(!rows.length)el('bosstiary-lista').append(node('p',onlyKilled&&!q?'Nenhum boss com kills ainda. Cadastre acima o total que você já tem.':'Nenhum boss encontrado.','dica'));
}
async function quickRun(intent,args,after=loadBosstiary){
 const status=el('assistente-feedback');
 try{const data=await execute(window.pywebview.api,intent,args,{...state.context},crypto.randomUUID());if(data.erro)throw new Error(data.erro);status.textContent=data.message||'Concluído.';await after();}
 catch(e){status.textContent=e.message||'Não foi possível concluir.';}
}
// Stamina agora: barra até 42h com as cores do Tibia (verde >= 39h, laranja >= 14h, vermelho abaixo).
const hhmm=m=>`${Math.floor(m/60)}:${String(m%60).padStart(2,'0')}`;
let staminaVersion=0;
async function renderStamina(){
 const version=++staminaVersion,context={...state.context};
 const r=await window.pywebview.api.assistente_executar('stamina.get',{},context);
 if(version!==staminaVersion||JSON.stringify(context)!==JSON.stringify(state.context))return;
 let minutes=null,text=r.erro&&!r.erro.startsWith('Registre')?r.erro:'Ao deslogar, digite a stamina abaixo (ou fale “estou deslogando, minha stamina está em 38 horas”).';
 if(!r.erro){
  const short=v=>new Date(v).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
  const ref=r.stamina,since=`desde ${short(ref.reference_at)} (há ${span(Date.now()-new Date(ref.reference_at))})`,when=v=>new Date(v)<=Date.now()?'já':short(v);
  if(ref.offline){minutes=r.estimate_minutes;text=`Offline ${since} · Verde (39h): ${when(r.green_at)} · Cheia (42h): ${when(r.full_at)}${new Date(r.full_at)>Date.now()?' · faltam '+span(new Date(r.full_at)-Date.now()):' · meta já atingida'}`;}
  else{minutes=ref.stamina_minutes;text=`Online ${since} · No login: ${hhmm(ref.stamina_minutes)} · Consumo real desconhecido; registre a stamina ao deslogar`;}
 }
 el('stamina-valor').textContent=minutes===null?'--:--':hhmm(minutes);
 const fill=el('stamina-fill');fill.style.width=`${(minutes||0)*100/2520}%`;fill.dataset.nivel=minutes>=2340?'verde':minutes>=840?'laranja':'vermelho';
 el('stamina-barra').setAttribute('aria-label',minutes===null?'Stamina sem referência':`Stamina ${hhmm(minutes)} de 42:00`);
 el('stamina-detalhe').textContent=(!r.erro?`Referência salva: ${hhmm(r.stamina.stamina_minutes)} · ${stamp(r.stamina.reference_at)}. `:'')+text+` · Atualização local: ${new Date().toLocaleTimeString('pt-BR')}`;
}
function select(module){ferramenta(module);for(const panel of document.querySelectorAll('[data-assistente-panel]'))panel.hidden=panel.dataset.assistentePanel!==module;for(const b of document.querySelectorAll('[data-assistente-tab]'))b.setAttribute('aria-pressed',String(b.dataset.assistenteTab===module));if(module==='overview'&&window.assistenteCanais)window.assistenteCanais.visivel();}
function ferramenta(module){active=module;if(module==='bosstiary'||module==='bosses'){bosstiaryKey='';}if(module==='upo'&&window.abrirUpo)window.abrirUpo();refresh();}
function boot(){
 if(booted||!el('assistente-context')||!window.pywebview||!window.pywebview.api)return;booted=true;
 for(const b of document.querySelectorAll('[data-assistente-tab]'))b.addEventListener('click',()=>select(b.dataset.assistenteTab));
 for(const [module,ops] of Object.entries(operations).filter(([module])=>module==='bosses')){const root=el('assistente-form-'+module);const wrap=node('label','Operação');const choice=node('select');choice.id='assistente-op-'+module;for(const [intent,title] of ops){const option=node('option',title);option.value=intent;choice.append(option);}choice.addEventListener('change',()=>renderFields(module));wrap.append(choice);const inputs=node('div',undefined,'voz-form assistente-fields');inputs.id='assistente-fields-'+module;const submit=node('button','Executar','btn btn-primary');submit.type='submit';root.append(wrap,inputs,submit);renderFields(module);root.addEventListener('submit',e=>{e.preventDefault();try{const values={};for(const key of ops.find(op=>op[0]===choice.value)[2]){const input=el(`assistente-${module}-${key}`);values[key]=input.type==='checkbox'?input.checked:input.value;}run(module,choice.value,payload(choice.value,values));}catch(error){el('assistente-feedback').textContent=error.message;}});}
 el('assistente-level-form').addEventListener('submit',async e=>{e.preventDefault();try{const context={...state.context};if(!el('assistente-level-confirm').checked)throw new Error('Marque a confirmação para alterar o cadastro.');const result=await window.pywebview.api.assistente_level(context.character_id,Number(el('assistente-level').value),true);if(result.erro)throw new Error(result.erro);el('assistente-feedback').textContent=result.message;el('assistente-level-confirm').checked=false;await refresh();}catch(error){el('assistente-feedback').textContent=error.message;}});
 el('bosstiary-form').addEventListener('submit',e=>{e.preventDefault();quickRun('bosstiary.set_total',{boss_id:el('bosstiary-boss').value.trim(),total_kills:Number(el('bosstiary-total').value)});});
 for(const input of document.querySelectorAll('[data-bosstiary-cat],#bosstiary-com-kills'))input.addEventListener('change',renderBosstiary);
 el('bosstiary-busca').addEventListener('input',renderBosstiary);
 el('cooldowns-busca').addEventListener('input',renderCooldowns);
 if(window.assistenteFerramentas)window.assistenteFerramentas.boot({run});
 bootConversion();
 el('assistente-world').addEventListener('input',()=>{pricesKey='';++pricesRevision;manualQuote('Mundo alterado. Valor manual em uso.');clearTimeout(pricesTimer);el('assistente-precos').replaceChildren(node('p','Aguardando o mundo…'));pricesTimer=setTimeout(()=>{refreshPrices(true);refreshQuote();},200);});
 if(typeof PERS_OUVINTES!=='undefined')PERS_OUVINTES.push(()=>{++refreshVersion;++bossLoadVersion;++staminaVersion;bosstiaryKey='';if(el('page-voz').classList.contains('shown'))refresh();});
 setInterval(()=>{if(active==='bosses'&&el('page-voz').classList.contains('shown'))tickCooldowns();},20000);
 select('overview');setInterval(()=>{if(el('page-voz').classList.contains('shown')&&!busy)refresh();},2000);
}
window.assistenteLoad=refresh;window.assistenteSelect=select;window.assistenteFerramenta=ferramenta;
if(typeof module!=='undefined'&&module.exports)module.exports={payload,execute,boot,bootConversion,refreshPrices,refreshQuote,manualQuote,decimalBR};
window.addEventListener('pywebviewready',boot);boot();
})();
