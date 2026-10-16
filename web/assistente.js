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
function table(rows,columns){const t=node('table',undefined,'assistente-table');const head=node('tr');for(const [,title] of columns)head.append(node('th',title));t.append(head);for(const row of rows){const tr=node('tr');for(const [key] of columns)tr.append(node('td',row[key]===null||row[key]===undefined?'—':String(row[key])));t.append(tr);}return t;}
function showResult(module,data){
 const out=el('assistente-result-'+module);out.replaceChildren();out.append(node('p',data.message||data.note||'Consulta concluída.'));
 if(data.range)out.append(node('strong',`Faixa: ${data.range[0]} a ${data.range[1]}${data.compatible===undefined?'':data.compatible?' · Compatível por level':' · Incompatível por level'}`));
 if(data.source)out.append(node('p',data.source,'dica'));
 if(data.timers)renderTimers(data.timers,out);
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
function renderTimers(timers,target){
 const list=target||el('assistente-timers-list');list.replaceChildren();
 for(const t of timers){const card=node('article',undefined,'card calmo');const remain=Math.max(0,Math.ceil((new Date(t.ends_at)-Date.now())/1000));card.append(node('strong',t.label),node('p',`${t.status==='active'?remain+' segundos':t.status==='completed'?'Concluído':'Cancelado'} · ${stamp(t.ends_at)} · ${t.character_id||'Global'}`));if(t.status==='active'){card.append(button('+1 min',()=>run('timers','timer.extend',{timer_id:t.id,delta_seconds:60})),button('Cancelar',()=>run('timers','timer.cancel',{timer_id:t.id})),button('Editar',()=>{el('assistente-op-timers').value='timer.edit';renderFields('timers',{timer_id:t.id,label:t.label,duration_seconds:t.duration_seconds});}));}card.append(button('Repetir',()=>run('timers','timer.repeat',{timer_id:t.id})));list.append(card);}
 if(!timers.length)list.append(node('p','Nenhum timer. Crie um pelo formulário ou por voz.','dica'));
}
function renderFields(module,initial={}){
 const intent=el('assistente-op-'+module).value;const keys=operations[module].find(op=>op[0]===intent)[2],container=el('assistente-fields-'+module);container.replaceChildren();
 for(const key of keys){const [caption,type]=fields[key],wrap=node('label',caption);let input;if(['boss','timer','offer','direction'].includes(type)){input=node('select');let options=type==='boss'?state.catalog.bosses.map(b=>[b.boss_id,b.name]):type==='timer'?state.timers.map(t=>[t.id,`${t.label} (${t.status})`]):type==='offer'?[['sell','Venda'],['buy','Compra'],['traded','Negociado']]:[['below','Abaixo de'],['above','Acima de']];for(const [v,title] of options){const option=node('option',title);option.value=v;input.append(option);}}else{input=node(type==='textarea'?'textarea':'input');if(type!=='textarea')input.type=type;}
 input.id=`assistente-${module}-${key}`;input.name=key;input.maxLength=key==='bosses'?30000:120;if(type==='number'){input.step='1';input.min='0';}if(type==='checkbox')input.checked=initial[key]===true;else if(initial[key]!==undefined)input.value=initial[key];else if(key==='days')input.value='30';else if(key==='item')input.value='Tibia Coin';else if(key==='duration_seconds')input.value='30';else if(key==='target_stamina_minutes'||key==='desired_stamina_minutes')input.value='2520';else if(key==='stamina_minutes'||key==='starting_stamina_minutes')input.value='2280';wrap.htmlFor=input.id;wrap.append(input);container.append(wrap);}
}
async function staminaDetails(context){
 const api=window.pywebview.api,ref=await api.assistente_executar('stamina.get',{},context);
 if(ref.erro||!ref.stamina.offline)return;
 const out=el('assistente-result-stamina'),cards=node('div',undefined,'voz-form'),rows=[];
 for(const target of [2340,2520]){const r=await api.assistente_executar('stamina.time_to',{target_stamina_minutes:target},context);if(!r.erro){const card=node('div',undefined,'card calmo');card.append(node('strong',`${target/60}h de stamina`),node('p',stamp(r.at)));cards.append(card);rows.push({price_gp:target,date:r.at});}}
 out.append(cards);const finish=rows.at(-1);if(!finish)return;
 const start=new Date(ref.stamina.reference_at),end=new Date(finish.date),timeline=[];
 for(let step=0;step<=4;step++){const at=new Date(start.getTime()+(end-start)*step/4).toISOString();const r=await api.assistente_executar('stamina.project',{target_datetime:at},context);if(!r.erro)timeline.push({price_gp:r.stamina_minutes,date:stamp(at),stamina:`${Math.floor(r.stamina_minutes/60)}h${String(r.stamina_minutes%60).padStart(2,'0')}`});}
 out.append(table(timeline,[['date','Horário estimado'],['stamina','Stamina se permanecer offline']]));chart(out,timeline,'Projeção de recuperação de stamina se permanecer offline');
}
async function run(module,intent,args){
 if(busy)return;busy=true;const status=el('assistente-feedback');status.textContent='Processando…';
 const context={...state.context},id=crypto.randomUUID();
 if(module==='market'&&el('assistente-world').value.trim())context.world_id=el('assistente-world').value.trim();
 try{const data=await execute(window.pywebview.api,intent,args,context,id);if(data.erro)throw new Error(data.erro);showResult(module,data);if(module==='stamina')await staminaDetails(context);status.textContent=data.message||'Concluído.';await refresh();}
 catch(e){status.textContent=e.message||'Não foi possível concluir.';}finally{busy=false;}
}
async function refresh(){
 if(!window.pywebview||!window.pywebview.api)return;
 try{const data=await window.pywebview.api.assistente_estado();if(data.erro)throw new Error(data.erro);state=data;
 for(const input of document.querySelectorAll('select[name=timer_id],select[name=boss_id]')){const previous=input.value;const rows=input.name==='timer_id'?data.timers.map(t=>[t.id,`${t.label} (${t.status})`]):data.catalog.bosses.map(b=>[b.boss_id,b.name]);const sig=rows.join('\n');if(input.dataset.sig===sig)continue;input.dataset.sig=sig;input.replaceChildren();for(const [value,title] of rows){const option=node('option',title);option.value=value;input.append(option);}if(rows.some(r=>r[0]===previous))input.value=previous;}
 if(!el('assistente-world').value)el('assistente-world').value=data.context.world_id||'';
 el('assistente-context').textContent=`Personagem: ${data.context.character_id||'Selecione em Meus personagens'} · Level: ${data.context.level||'—'} · Mundo: ${data.context.world_id||'Não informado'}`;el('assistente-overview').textContent=`${data.timers.filter(t=>t.status==='active').length} timers ativos · Bosses e stamina por personagem · Market privado por mundo. Alertas funcionam enquanto o aplicativo está aberto e são reconciliados uma vez ao reabrir.`;renderTimers(data.timers);
 const names=el('bosstiary-nomes');if(names&&names.children.length!==data.catalog.bosses.length)names.replaceChildren(...data.catalog.bosses.map(b=>{const o=node('option');o.value=b.name;return o;}));
 const key=`${data.context.character_id}|${data.revision}`;if(['bosstiary','bosses'].includes(active)&&key!==bosstiaryKey){bosstiaryKey=key;await loadBosstiary();}
 if(active==='stamina')await renderStamina();}
 catch(e){el('assistente-feedback').textContent=e.message;}
}
// Bosstiary: lista do personagem em uso, no estilo da Cyclopedia do Tibia.
const STAR_NAMES=['Prowess','Expertise','Mastery'];let bosstiaryRows=[],bosstiaryKey='';
const bossImage=name=>`assets/creatures/${name.split(' (')[0].toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_|_$/g,'')}.gif`;
async function loadBosstiary(){
 const out=el('bosstiary-lista');
 if(!state.context.character_id){bosstiaryRows=[];renderCooldowns();out.replaceChildren(node('p','Selecione um personagem em Meus personagens.','dica'));return;}
 const data=await window.pywebview.api.assistente_executar('boss.cooldown.list',{},{...state.context});
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
async function renderStamina(){
 const r=await window.pywebview.api.assistente_executar('stamina.get',{},{...state.context});
 let minutes=null,text=r.erro&&!r.erro.startsWith('Registre')?r.erro:'Ao deslogar, digite a stamina abaixo (ou fale “estou deslogando, minha stamina está em 38 horas”).';
 if(!r.erro){
  const short=v=>new Date(v).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
  const ref=r.stamina,since=`desde ${short(ref.reference_at)} (há ${span(Date.now()-new Date(ref.reference_at))})`,when=v=>new Date(v)<=Date.now()?'já':short(v);
  if(ref.offline){minutes=r.estimate_minutes;text=`Offline ${since} · Verde (39h): ${when(r.green_at)} · Cheia (42h): ${when(r.full_at)}`;}
  else{minutes=Math.max(0,ref.stamina_minutes-r.online_minutes);text=`Online ${since} · No login: ${hhmm(ref.stamina_minutes)} · A barra mostra quanto sobra se você caçou o tempo todo`;}
 }
 el('stamina-valor').textContent=minutes===null?'--:--':hhmm(minutes);
 const fill=el('stamina-fill');fill.style.width=`${(minutes||0)*100/2520}%`;fill.dataset.nivel=minutes>=2340?'verde':minutes>=840?'laranja':'vermelho';
 el('stamina-barra').setAttribute('aria-label',minutes===null?'Stamina sem referência':`Stamina ${hhmm(minutes)} de 42:00`);
 el('stamina-detalhe').textContent=text;
}
function select(module){active=module;if(module==='bosstiary'||module==='bosses'){bosstiaryKey='';}for(const panel of document.querySelectorAll('[data-assistente-panel]'))panel.hidden=panel.dataset.assistentePanel!==module;for(const b of document.querySelectorAll('[data-assistente-tab]'))b.setAttribute('aria-pressed',String(b.dataset.assistenteTab===module));refresh();}
function boot(){
 if(booted||!el('assistente-context')||!window.pywebview||!window.pywebview.api)return;booted=true;
 for(const b of document.querySelectorAll('[data-assistente-tab]'))b.addEventListener('click',()=>select(b.dataset.assistenteTab));
 for(const [module,ops] of Object.entries(operations)){const root=el('assistente-form-'+module);const wrap=node('label','Operação');const choice=node('select');choice.id='assistente-op-'+module;for(const [intent,title] of ops){const option=node('option',title);option.value=intent;choice.append(option);}choice.addEventListener('change',()=>renderFields(module));wrap.append(choice);const inputs=node('div',undefined,'voz-form assistente-fields');inputs.id='assistente-fields-'+module;const submit=node('button','Executar','btn btn-primary');submit.type='submit';root.append(wrap,inputs,submit);renderFields(module);root.addEventListener('submit',e=>{e.preventDefault();try{const values={};for(const key of ops.find(op=>op[0]===choice.value)[2]){const input=el(`assistente-${module}-${key}`);values[key]=input.type==='checkbox'?input.checked:input.value;}run(module,choice.value,payload(choice.value,values));}catch(error){el('assistente-feedback').textContent=error.message;}});}
 el('assistente-level-form').addEventListener('submit',async e=>{e.preventDefault();try{const context={...state.context};if(!el('assistente-level-confirm').checked)throw new Error('Marque a confirmação para alterar o cadastro.');const result=await window.pywebview.api.assistente_level(context.character_id,Number(el('assistente-level').value),true);if(result.erro)throw new Error(result.erro);el('assistente-feedback').textContent=result.message;el('assistente-level-confirm').checked=false;await refresh();}catch(error){el('assistente-feedback').textContent=error.message;}});
 el('bosstiary-form').addEventListener('submit',e=>{e.preventDefault();quickRun('bosstiary.set_total',{boss_id:el('bosstiary-boss').value.trim(),total_kills:Number(el('bosstiary-total').value)});});
 for(const input of document.querySelectorAll('[data-bosstiary-cat],#bosstiary-com-kills'))input.addEventListener('change',renderBosstiary);
 el('bosstiary-busca').addEventListener('input',renderBosstiary);
 el('cooldowns-busca').addEventListener('input',renderCooldowns);
 el('stamina-rapido').addEventListener('submit',e=>{e.preventDefault();const [h,m='0']=el('stamina-hhmm').value.trim().split(':');const minutes=Number(h)*60+Number(m);
  if(!Number.isInteger(minutes)||Number(m)>59||minutes>2520){el('assistente-feedback').textContent='Digite como no jogo, por exemplo 41:21 (máximo 42:00).';return;}
  quickRun('stamina.logout',{stamina_minutes:minutes},renderStamina);});
 el('stamina-logar').addEventListener('click',()=>quickRun('stamina.login',{},renderStamina));
 setInterval(()=>{if(active==='bosses'&&el('page-voz').classList.contains('shown'))tickCooldowns();},20000);
 select('overview');setInterval(()=>{if(el('page-voz').classList.contains('shown')&&!busy)refresh();},2000);
}
window.assistenteLoad=refresh;window.assistenteSelect=select;
if(typeof module!=='undefined'&&module.exports)module.exports={payload,execute,boot};
window.addEventListener('pywebviewready',boot);boot();
})();
