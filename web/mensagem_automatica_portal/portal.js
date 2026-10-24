'use strict';
// Credencial somente em memória; nenhuma configuração ou token vai para a URL.
(()=>{
 const $=id=>document.getElementById(id);
 let connection='',connected=false,groups=[],subscriptions=[],runs=[],editing=null,mode='simulation',qrTimer,configurationData=null,recoveryTimer,recoveryEpoch=0,closed=false,armed='';
 const BLOCKS=[['dia','Data'],['saudacao','Saudação'],['frase','Mensagem do dia'],['mundo','Mundo'],['calendario','Eventos do Tibia'],['yasir','Yasir (consulta online)'],['rashid','Rashid'],['criatura','Criatura boostada'],['boss','Boss boostado'],['dream','Dream Court'],['dream_mortes','Dream Court — mortes (Last Day)'],['mudancas_online','Outras world changes (consulta online)'],['server_save','Próximo SS']];
 const FIELDS=[['comunidade','Comunidade'],['assinatura','Assinatura'],['deeplings','Boss Deeplings'],['regiao','Região boostada'],['roshamuul','Roshamuul / robôs'],['drome','Tibia Drome (fim da rotação)'],['coin_compra','TC: comprar (gp)'],['coin_venda','TC: vender (gp)'],['coin_hora','Horário dos preços']];
 const EXTRAS=[['noticias','O que rolou em Tibia (notícias e avisos)',''],['kill','Top 10 criaturas mortas ontem','mundo'],['exp_mundo','Top 10 XP do servidor (ontem)','mundo'],['exp_guild','Top XP da guild (ontem)','guild'],['guild','Resumo da guild','guild'],['online_guild','Online da guild','guild'],['char','Personagem (ficha e mortes recentes)','personagem'],['transfer','Transferências de mundo (10 dias)','mundo']];
 const NEW_BLOCKS=['dia','saudacao','frase','mundo','server_save'];
 const notice=text=>$('notice').textContent=text;
 const TABS=['geral','rotinas','alertas','comandos','conexao','historico'];
 function goTab(name){
  if(name==='acesso'){const d=$('access-controls');d.open=true;d.scrollIntoView({block:'start'});return;}
  if(!TABS.includes(name))return;
  document.querySelectorAll('.tabbtn[data-tab]').forEach(b=>b.classList.toggle('on',b.dataset.tab===name));
  TABS.forEach(t=>{$('tab-'+t).hidden=t!==name;});
  if(name==='geral')renderOverview();
 }
 const clearQR=()=>{clearTimeout(qrTimer);$('qr').hidden=true;$('qr').removeAttribute('src');};
 function clearRecovery(){recoveryEpoch++;clearTimeout(recoveryTimer);$('recovery-code').textContent='';$('recovery-input').value='';}
 function logout(){closed=true;$('access-controls').hidden=true;clearQR();clearRecovery();connection='';groups=[];subscriptions=[];runs=[];editing=null;configurationData=null;$('routines').replaceChildren();watches=[];$('watches').replaceChildren();botgroups=[];$('botgroups').replaceChildren();$('ov-groups').replaceChildren();$('kpis').replaceChildren();$('ov-activity').replaceChildren();$('settings').hidden=true;notice('Gestão encerrada. Feche esta janela.');}
 async function api(path,method='GET',body){
  const result=await window.pywebview.api.request('/v1/'+path,method,body||null);
  if(result.error)throw Error(result.error);return result.data;
 }
 const guarded=fn=>async()=>{try{await fn();}catch(e){notice(e.message||'Falha na operação.');}};
 const stateLabel=state=>({active:'Ativa',inactive:'Pausada',connected:'Conectado',disconnected:'Desconectado',pairing:'Aguardando pareamento',revoked:'Revogada',pending:'Aguardando geração',preparing:'Gerando',ready:'Aguardando horário de envio',sending:'Envio em andamento',simulated:'Simulado — sem envio',accepted:'Aceito pelo WhatsApp — leitura não confirmada',uncertain:'Resultado incerto — não reenviar sem conferir',expired:'Expirado',cancelled:'Cancelado',failed:'Não concluído'})[state]||'Situação indisponível';
 const text=value=>typeof value==='string'?value.slice(0,200):'';
 const time=value=>typeof value==='string'&&/^([01]\d|2[0-3]):[0-5]\d$/.test(value)?value:'';
 const el=(tag,className,content)=>{const e=document.createElement(tag);if(className)e.className=className;if(content!==undefined)e.textContent=content;return e;};
 const day=ref=>/^\d{4}-\d{2}-\d{2}$/.test(ref||'')?ref.split('-').reverse().join('/'):'Data indisponível';
 const schedule=c=>c.generateAt&&c.sendAt?'Gera '+text(c.generateAt)+' · Envia '+text(c.sendAt)+' · '+(text(c.timezone)||'sem fuso'):'Sem horário definido';
 function renderRuns(items,title){
  goTab('historico');$('runs-card').hidden=false;$('runs-title').textContent=title;const root=$('runs-result');root.replaceChildren();
  if(!items.length)root.append(el('p','muted','Nenhuma execução registrada.'));
  else{const list=document.createElement('ul');for(const item of items)list.append(el('li','',day(item.reference)+' · '+stateLabel(item.state)));root.append(list);}
  $('runs-card').scrollIntoView({block:'nearest'});
 }
 function showPreview(r){goTab('rotinas');$('preview-card').hidden=false;$('preview-result').textContent=r.text;$('preview-card').scrollIntoView({block:'nearest'});notice('Prévia gerada. Nenhum envio realizado.');}
 function options(element,items,first){element.replaceChildren(new Option(first,''));for(const item of items)element.add(new Option(item.label||item.id,item.id));}
 function renderGroups(preferLabel){
  const query=$('group-search').value.trim().toLowerCase(),current=$('groups').value;
  const list=groups.filter(g=>!query||String(g.label||'').toLowerCase().includes(query));
  options($('groups'),list,list.length?'Escolha um grupo':'Nenhum grupo encontrado');
  const keep=list.find(g=>g.id===current)||(preferLabel&&list.find(g=>g.label===preferLabel));
  if(keep)$('groups').value=keep.id;
 }
 // Editor de rotina: o mesmo formulário cria e edita; tudo via DOM, sem HTML montado com dados.
 function tick(parent,group,key,label,checked){const l=el('label','tick'),i=document.createElement('input');i.type='checkbox';i.dataset.group=group;i.dataset.key=key;i.checked=checked;l.append(i,document.createTextNode(label));parent.append(l);}
 function field(kind,key,value,max,placeholder,label){const i=document.createElement('input');i.dataset[kind]=key;i.maxLength=max;i.value=value;i.placeholder=placeholder;i.setAttribute('aria-label',label);return i;}
 function openEditor(s,preferLabel){goTab('rotinas');
  editing=s;const c=s?s.config||{}:configurationData||{},on=(g,k)=>c[g]?.[k]===true,val=(g,k,max)=>typeof c[g]?.[k]==='string'?c[g][k].slice(0,max):'';
  $('editor-title').textContent=s?'Editar rotina · '+(text(s.destinationLabel)||'grupo'):'Nova rotina';
  $('ed-personagem').value=text(c.personagem).slice(0,40);$('ed-mundo').value=text(c.mundo).slice(0,40);
  $('ed-generate').value=time(c.generateAt);$('ed-send').value=time(c.sendAt);
  $('ed-zone').value=text(c.timezone).slice(0,100)||Intl.DateTimeFormat().resolvedOptions().timeZone||'';
  $('ed-manual').value=/^\d{4}-\d{2}-\d{2}$/.test(c.manualDate||'')?c.manualDate:'';
  const blocks=$('ed-blocks');blocks.replaceChildren();for(const [k,label] of BLOCKS)tick(blocks,'blocks',k,label,c.blocks?on('blocks',k):NEW_BLOCKS.includes(k));
  const fields=$('ed-fields');fields.replaceChildren();
  for(const [k,label] of FIELDS){const row=el('div','row');tick(row,'fields',k,label,on('fields',k));row.append(field('value',k,val('values',k,200),200,'Valor',label+': valor'));fields.append(row);}
  const extras=$('ed-extras');extras.replaceChildren();
  for(const [k,label,kind] of EXTRAS){const row=el('div','row');tick(row,'extras',k,label,on('extras',k));if(kind)row.append(field('arg',k,val('args',k,40),40,'Padrão: '+(kind==='guild'?'guild do personagem':kind==='mundo'?'mundo acima':'personagem acima'),label+': outro '+kind+' (opcional)'));extras.append(row);}
  $('group-search').value='';renderGroups(s?.destinationLabel||preferLabel);
  $('editor').hidden=false;$('editor').scrollIntoView({block:'start'});
 }
 function closeEditor(){editing=null;$('editor').hidden=true;}
 function collect(){
  const c={personagem:$('ed-personagem').value.trim(),mundo:$('ed-mundo').value.trim(),blocks:{},fields:{},values:{},extras:{},args:{},generateAt:$('ed-generate').value,sendAt:$('ed-send').value,timezone:$('ed-zone').value.trim(),manualDate:$('ed-manual').value};
  $('editor').querySelectorAll('input[data-group]').forEach(i=>{c[i.dataset.group][i.dataset.key]=i.checked;});
  $('editor').querySelectorAll('input[data-value]').forEach(i=>{c.values[i.dataset.value]=i.value.trim();});
  $('editor').querySelectorAll('input[data-arg]').forEach(i=>{c.args[i.dataset.arg]=i.value.trim();});
  return c;
 }
 async function saveRoutine(active){
  if(!connection||!connected)throw Error('Conecte seu WhatsApp antes de salvar.');
  if(!$('groups').value)throw Error('Escolha o grupo de destino.');
  const config=collect(),dest=await api('destinations','POST',{connection,group:$('groups').value}),body={config,connection,destination:dest.id,active};
  if(editing)await api('subscriptions/'+editing.id,'PUT',body);else await api('subscriptions','POST',body);
  closeEditor();await loadRoutines();
  notice(mode==='simulation'?(active?'Agenda de simulação ativada. Nenhuma mensagem real será enviada.':'Configuração de simulação salva e pausada.'):(active?'Rotina salva e ativa: '+schedule(config)+'.':'Rotina salva e pausada.'));
 }
 const routineBody=(s,config,active)=>({config,connection:s.connection,destination:s.destination,active});
 async function loadRoutines(){[subscriptions,runs]=await Promise.all([api('subscriptions'),api('runs')]);renderRoutines();renderOverview();}
 function renderRoutines(){
  const root=$('routines');root.replaceChildren();$('routine-count').textContent=subscriptions.length+' de 5';
  if(!subscriptions.length){root.append(el('p','muted','Nenhuma rotina ainda. Clique em "+ Nova rotina".'));return;}
  for(const s of subscriptions){
   const c=s.config||{},on=s.state==='active',name=text(s.destinationLabel)||'Grupo sem nome',last=runs.find(r=>r.subscription===s.id&&(r.state==='accepted'||r.state==='simulated'));
   const card=el('article','routine'+(on?' on':'')),head=el('div','routine-head');
   head.append(el('span','badge '+(on?'good':''),stateLabel(s.state)),el('h3','',name));
   if(s.source==='group')head.append(el('span','badge','criado pelo grupo'));
   else if(s.changedByGroup)head.append(el('span','badge','ajustado pelo grupo'));
   card.append(head,el('p','',schedule(c)),el('p','muted',(text(c.personagem)||'Sem personagem')+' · '+(text(c.mundo)||'Sem mundo')),el('p','muted','Último envio: '+(last?day(last.reference)+' · '+stateLabel(last.state):'nenhum ainda')));
   const actions=el('div','actions');
   const add=(label,fn,className)=>{const b=el('button',className,label);b.type='button';b.onclick=guarded(()=>fn(b));actions.append(b);};
   add('Editar',async()=>openEditor(s),'primary');
   add(on?'Pausar':'Ativar',()=>toggleRoutine(s));
   add('Prévia',async()=>showPreview(await api('preview','POST',s.config)));
   add('Histórico',async()=>renderRuns(runs.filter(r=>r.subscription===s.id),'Histórico · '+name));
   // Exclusão em dois cliques: o primeiro só arma por 5 segundos.
   add('Excluir',async b=>{
    if(armed!==s.id){armed=s.id;b.textContent='Confirmar exclusão';setTimeout(()=>{if(armed===s.id){armed='';b.textContent='Excluir';}},5000);return;}
    armed='';await api('subscriptions/'+s.id,'DELETE');if(editing?.id===s.id)closeEditor();await loadRoutines();notice('Rotina excluída.');
   },'danger');
   card.append(actions);root.append(card);
  }
 }
 function setConnection(label,tone,detail){const b=$('connection-state');b.textContent=label;b.className='badge '+tone;$('connection-detail').textContent=detail;$('pair-box').hidden=connected;$('revoke').hidden=!connection;renderOverview();}
 async function refresh(){
  clearQR();const list=await api('connections');const current=list.find(c=>c.state!=='revoked');connection=current?.id||'';connected=false;groups=[];renderGroups();
  if(!connection){setConnection('Desconectado','bad','Nenhuma conexão ativa. Aceite os riscos e conecte seu WhatsApp.');return;}
  const status=await api('connections/'+connection);connected=status.state==='connected';
  setConnection((mode==='simulation'?'Simulação · ':'')+stateLabel(status.state),connected?'good':status.state==='pairing'?'warn':'bad',connected?'':'Escaneie o QR no celular: WhatsApp › Aparelhos conectados.');
  if(status.qrImage&&status.expiresAt>Date.now()/1000&&/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(status.qrImage)){
   $('qr').src=status.qrImage;$('qr').hidden=false;qrTimer=setTimeout(clearQR,Math.min((status.expiresAt-Date.now()/1000)*1000,90000));
  }
  if(connected){
   // Sem a lista de grupos (o WhatsApp às vezes demora a responder) o resto da tela continua: rotinas e alertas seguem salvos.
   try{groups=await api('connections/'+connection+'/groups');}catch(error){$('connection-detail').textContent='Não foi possível listar os grupos agora ('+error.message+'). Suas rotinas, alertas e comandos continuam salvos; use "Atualizar" em instantes.';return;}
   renderGroups(editing?.destinationLabel);options($('watch-groups'),groups,'Escolha um grupo');options($('bot-groups'),groups,'Escolha um grupo');$('connection-detail').textContent=groups.length+' grupos disponíveis para envio.';renderOverview();}
 }
 // Alertas da guild: o servidor detecta mortes e marcos de level e envia um aviso por evento; aqui só se configura.
 let watches=[];
 const watchBody=(w,active)=>({guild:w.guild,milestone:w.milestone,deaths:w.deaths,ups:w.ups,hourlyCap:w.hourlyCap,perMinute:w.perMinute,connection:w.connection,destination:w.destination,active});
 async function loadWatches(){watches=await api('watches');renderWatches();renderOverview();}
 function renderWatches(){
  const root=$('watches');root.replaceChildren();$('watch-count').textContent=watches.length+' de 3';
  for(const w of watches){
   const on=w.state==='active',card=el('article','routine'+(on?' on':'')),head=el('div','routine-head');
   head.append(el('span','badge '+(on?'good':''),stateLabel(w.state)),el('h3','',text(w.guild)+' → '+(text(w.destinationLabel)||'Grupo sem nome')));
   if(w.source==='group')head.append(el('span','badge','criado pelo grupo'));
   else if(w.changedByGroup)head.append(el('span','badge','ajustado pelo grupo'));
   card.append(head,el('p','muted',[w.deaths?'Mortes':'',w.ups?(Number(w.milestone)===1?'Todo level up':'Level ups a cada '+Number(w.milestone)):''].filter(Boolean).join(' · ')+(Number(w.hourlyCap)===0?' · sem limite por hora':' · até '+Number(w.hourlyCap)+' avisos/hora')+' · até '+Number(w.perMinute||3)+' por minuto'));
   const actions=el('div','actions');
   const add=(label,fn,className)=>{const b=el('button',className,label);b.type='button';b.onclick=guarded(()=>fn(b));actions.append(b);};
   add(on?'Pausar':'Ativar',()=>toggleWatch(w));
   add('Excluir',async b=>{
    if(armed!==w.id){armed=w.id;b.textContent='Confirmar exclusão';setTimeout(()=>{if(armed===w.id){armed='';b.textContent='Excluir';}},5000);return;}
    armed='';await api('watches/'+w.id,'DELETE');await loadWatches();notice('Alerta excluído.');
   },'danger');
   card.append(actions);root.append(card);
  }
 }
 $('watch-save').onclick=guarded(async()=>{
  if(!connection||!connected)throw Error('Conecte seu WhatsApp antes de salvar.');
  if(!$('watch-groups').value)throw Error('Escolha o grupo de destino.');
  // Os mesmos limites do servidor, com aviso claro: a recusa dele aparece só como "pedido recusado".
  const milestone=Number($('watch-milestone').value),cap=Number($('watch-cap').value),perMinute=Number($('watch-minute').value);
  if(!$('watch-guild').value.trim())throw Error('Informe o nome da guild.');
  if(!Number.isInteger(milestone)||milestone<1||milestone>1000)throw Error('Level up a cada: use um número de 1 a 1000 (1 = todo level).');
  if(!Number.isInteger(cap)||cap<0||cap>1000)throw Error('Máximo de avisos por hora: use um número de 0 a 1000 (0 = sem limite).');
  if(!Number.isInteger(perMinute)||perMinute<1||perMinute>120)throw Error('Máximo de avisos por minuto: use um número de 1 a 120.');
  if(!$('watch-deaths').checked&&!$('watch-ups').checked)throw Error('Marque mortes, level ups ou os dois.');
  const dest=await api('destinations','POST',{connection,group:$('watch-groups').value});
  await api('watches','POST',{guild:$('watch-guild').value.trim(),milestone:Number($('watch-milestone').value),deaths:$('watch-deaths').checked,ups:$('watch-ups').checked,hourlyCap:cap,perMinute,connection,destination:dest.id,active:true});
  $('watch-guild').value='';await loadWatches();
  notice(mode==='simulation'?'Alerta de simulação ativado. Nenhuma mensagem real será enviada.':'Alerta ativado. Os avisos começam na próxima varredura (cerca de 2 minutos); o que já aconteceu antes não é enviado.');
 });
 // Comandos no grupo: o servidor lê só as linhas que começam com "!" e responde; aqui só se configura.
 let botgroups=[];
 const botBody=(g,active,groupConfig=g.groupConfig!==false)=>({world:g.world,cooldown:g.cooldown,connection:g.connection,destination:g.destination,active,groupConfig});
 // 30 → 30 s · 120 → 2 min · 3600 → 1 h
 const duration=s=>s>=3600&&s%3600===0?s/3600+' h':s>=60&&s%60===0?s/60+' min':s+' s';
 // "30", "30s", "2m" ou "1h" → segundos (3 s a 24 h), como no !set cooldown do grupo
 function parseDuration(value){const m=/^(\d{1,6})\s*([smh]?)$/i.exec(String(value).trim());if(!m)return NaN;const n=Number(m[1])*({s:1,m:60,h:3600}[(m[2]||'s').toLowerCase()]);return n>=3&&n<=86400?n:NaN;}
 async function loadBotgroups(){botgroups=await api('botgroups');renderBotgroups();renderOverview();}
 function renderBotgroups(){
  const root=$('botgroups');root.replaceChildren();$('bot-count').textContent=botgroups.length+' de 3';
  for(const g of botgroups){
   const on=g.state==='active',card=el('article','routine'+(on?' on':'')),head=el('div','routine-head');
   head.append(el('span','badge '+(on?'good':''),stateLabel(g.state)),el('h3','',text(g.destinationLabel)||'Grupo sem nome'));
   if(g.paused)head.append(el('span','badge','pausado pelo grupo'));
   if(g.changedByGroup)head.append(el('span','badge','ajustado pelo grupo'));
   const extra=[Array.isArray(g.disabled)&&g.disabled.length?'desligados aqui: '+g.disabled.map(text).join(', '):'',g.groupConfig===false?'configuração pelo grupo bloqueada':'admins do grupo podem configurar (!set)'].filter(Boolean).join(' · ');
   card.append(head,el('p','muted','Mundo padrão: '+text(g.world)+' · 1 comando a cada '+duration(Number(g.cooldown))+' por membro · '+extra));
   const actions=el('div','actions');
   const add=(label,fn,className)=>{const b=el('button',className,label);b.type='button';b.onclick=guarded(()=>fn(b));actions.append(b);};
   add(g.paused?'Retomar comandos':(on?'Pausar':'Ativar'),()=>toggleBot(g));
   add(g.groupConfig===false?'Permitir configuração pelo grupo':'Bloquear configuração pelo grupo',()=>toggleBotConfig(g));
   add('Excluir',async b=>{
    if(armed!==g.id){armed=g.id;b.textContent='Confirmar exclusão';setTimeout(()=>{if(armed===g.id){armed='';b.textContent='Excluir';}},5000);return;}
    armed='';await api('botgroups/'+g.id,'DELETE');await loadBotgroups();notice('Comandos excluídos.');
   },'danger');
   card.append(actions);root.append(card);
  }
 }
 $('bot-save').onclick=guarded(async()=>{
  if(!connection||!connected)throw Error('Conecte seu WhatsApp antes de salvar.');
  if(!$('bot-groups').value)throw Error('Escolha o grupo de destino.');
  const world=$('bot-world').value.trim(),cooldown=parseDuration($('bot-cooldown').value);
  if(!/^[A-Za-z]{2,40}$/.test(world))throw Error('Informe o mundo padrão, só com letras (ex.: Rasteibra).');
  if(!Number.isInteger(cooldown))throw Error('Intervalo por membro: de 3 segundos a 24 horas (ex.: 30, 30s, 2m, 1h).');
  const dest=await api('destinations','POST',{connection,group:$('bot-groups').value});
  await api('botgroups','POST',{world,cooldown,connection,destination:dest.id,active:true,groupConfig:$('bot-config').checked});
  await loadBotgroups();
  notice(mode==='simulation'?'Comandos de simulação ativados. Nenhuma mensagem real será enviada.':'Comandos ativados. Use !help no grupo para testar.');
 });
 // ---- Visão geral: um cartão por grupo, com os 3 bots e ações rápidas (as mesmas das listas) ----
 const toggleRoutine=async s=>{const on=s.state==='active';await api('subscriptions/'+s.id,'PUT',routineBody(s,s.config,!on));await loadRoutines();notice(on?'Rotina pausada.':'Rotina ativada.');};
 const toggleWatch=async w=>{const on=w.state==='active';await api('watches/'+w.id,'PUT',watchBody(w,!on));await loadWatches();notice(on?'Alerta pausado.':'Alerta ativado.');};
 const toggleBot=async g=>{
  if(g.paused){await api('botgroups/'+g.id,'PUT',{...botBody(g,true),paused:false});await loadBotgroups();notice('Comandos retomados.');return;}
  const on=g.state==='active';await api('botgroups/'+g.id,'PUT',botBody(g,!on));await loadBotgroups();notice(on?'Comandos pausados.':'Comandos ativados.');
 };
 const toggleBotConfig=async g=>{const on=g.state==='active';await api('botgroups/'+g.id,'PUT',botBody(g,on,g.groupConfig===false));await loadBotgroups();notice(g.groupConfig===false?'Admins do grupo podem configurar com !set, !alerta e !bomdia.':'Configuração pelo grupo bloqueada.');};
 let filtro='todos';
 const when=epoch=>typeof epoch==='number'&&epoch>0?new Date(epoch*1000).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'nunca';
 function pickLabel(select,label){const o=[...select.options].find(x=>x.textContent===label);if(o)select.value=o.value;}
 function groupRows(){
  const map=new Map(),get=(destino,label)=>{const key=text(destino);if(!map.has(key))map.set(key,{grupo:'',comandos:null,alerta:null,bomdia:null});const r=map.get(key);if(!r.grupo)r.grupo=text(label);return r;};
  for(const g of botgroups)get(g.destination,g.destinationLabel).comandos=g;
  for(const w of watches)get(w.destination,w.destinationLabel).alerta=w;
  for(const s of subscriptions)get(s.destination,s.destinationLabel).bomdia=s;
  return [...map.values()].map(r=>({...r,grupo:r.grupo||'Grupo sem nome'})).sort((a,b)=>a.grupo.localeCompare(b.grupo,'pt-BR'));
 }
 const botOn=g=>!!g&&g.state==='active'&&!g.paused,itemOn=i=>!!i&&i.state==='active';
 function box(titulo,tom,badge,linhas,botoes){
  const b=el('div','bot '+tom),head=el('div','bot-head');head.append(el('strong','',titulo));if(badge)head.append(el('span','badge '+(tom==='on'?'good':''),badge));b.append(head);
  for(const l of linhas.filter(Boolean))b.append(el('p','muted',l));
  if(botoes.length){const a=el('div','actions');for(const [label,fn,cls] of botoes){const x=el('button',cls||'',label);x.type='button';x.onclick=guarded(()=>fn(x));a.append(x);}b.append(a);}
  return b;
 }
 const origem=i=>i&&i.source==='group'?'criado pelo grupo':i&&i.changedByGroup?'ajustado pelo grupo':'';
 function groupCard(r){
  const live=botOn(r.comandos)||itemOn(r.alerta)||itemOn(r.bomdia),card=el('article','gcard'+(live?' live':'')),head=el('div','gcard-head');
  head.append(el('h3','',r.grupo));card.append(head);
  const bots=el('div','bots');card.append(bots);
  const c=r.comandos,a=r.alerta,s=r.bomdia;
  bots.append(c?box('🤖 Comandos',botOn(c)?'on':'off',c.paused?'pausado pelo grupo':botOn(c)?'ativo':'pausado',
   ['Mundo '+text(c.world)+' · 1 comando a cada '+duration(Number(c.cooldown))+' por membro',Array.isArray(c.disabled)&&c.disabled.length?'Desligados aqui: '+c.disabled.map(text).join(', '):'','Último uso: '+when(c.lastUse),c.groupConfig===false?'Configuração pelo grupo bloqueada':'Admins do grupo podem configurar',origem(c)],
   [[c.paused?'Retomar comandos':(botOn(c)?'Pausar':'Ativar'),()=>toggleBot(c)],[c.groupConfig===false?'Permitir configuração pelo grupo':'Bloquear configuração pelo grupo',()=>toggleBotConfig(c)]])
   :box('🤖 Comandos','none','',['Não configurado neste grupo.'],[['Configurar',()=>{goTab('comandos');pickLabel($('bot-groups'),r.grupo);$('bot-world').focus();}]]));
  bots.append(a?box('🚨 Alerta da guild',itemOn(a)?'on':'off',itemOn(a)?'ativo':'pausado',
   ['Guild '+text(a.guild),(a.deaths?'Mortes':'')+(a.ups?(a.deaths?' · ':'')+(Number(a.milestone)===1?'todo level up':'level up a cada '+Number(a.milestone)):''),(Number(a.hourlyCap)===0?'Sem limite por hora':'Até '+Number(a.hourlyCap)+' por hora')+' · até '+Number(a.perMinute||3)+' por minuto','Último aviso: '+when(a.lastSent),origem(a)],
   [[itemOn(a)?'Pausar':'Ativar',()=>toggleWatch(a)]])
   :box('🚨 Alerta da guild','none','',['Nenhum alerta neste grupo.'],[['Configurar',()=>{goTab('alertas');pickLabel($('watch-groups'),r.grupo);$('watch-guild').focus();}]]));
  const last=s?runs.find(x=>x.subscription===s.id&&(x.state==='accepted'||x.state==='simulated')):null;
  bots.append(s?box('☀️ Bom dia',itemOn(s)?'on':'off',itemOn(s)?'ligado':'pausado',
   [schedule(s.config||{}),(text((s.config||{}).personagem)||'Sem personagem')+' · '+(text((s.config||{}).mundo)||'Sem mundo'),'Último envio: '+(last?day(last.reference):'nenhum ainda'),origem(s)],
   [[itemOn(s)?'Pausar':'Ativar',()=>toggleRoutine(s)],['Editar',async()=>openEditor(s)],['Prévia',async()=>showPreview(await api('preview','POST',s.config))],['Histórico',async()=>renderRuns(runs.filter(x=>x.subscription===s.id),'Histórico · '+r.grupo)]])
   :box('☀️ Bom dia','none','',['Sem rotina de bom dia neste grupo.'],[['Criar rotina',async()=>openEditor(null,r.grupo)]]));
  return card;
 }
 function kpi(label,value,hint,tone){const k=el('div','kpi');k.append(el('div','label',label),el('div','value'+(tone?' '+tone:''),String(value)),el('div','hint',hint));return k;}
 function meterKpi(label,used,max){
  const free=max-used,k=kpi(label,used+' de '+max,used>=max?'limite atingido':free+(free===1?' vaga livre':' vagas livres'),used>=max?'warn':'');
  const m=document.createElement('meter');m.min=0;m.max=max;m.value=used;m.low=max-0.5;m.high=max-0.5;m.optimum=0;m.setAttribute('aria-label',label+': '+used+' de '+max);k.append(m);return k;
 }
 function activity(){
  const root=$('ov-activity');root.replaceChildren();
  const days=new Map();for(const r of runs){if(!/^\d{4}-\d{2}-\d{2}$/.test(r.reference||''))continue;const d=days.get(r.reference)||{ok:0,bad:0};if(r.state==='accepted'||r.state==='simulated')d.ok++;else if(['failed','expired','uncertain'].includes(r.state))d.bad++;days.set(r.reference,d);}
  const list=[...days.entries()].sort((a,b)=>a[0].localeCompare(b[0])).slice(-14).filter(([,d])=>d.ok||d.bad);
  if(!list.length){root.setAttribute('aria-label','Nenhum envio de bom dia ainda');root.append(el('p','muted','Nenhum envio de bom dia registrado ainda.'));return;}
  const max=Math.max(...list.map(([,d])=>d.ok+d.bad)),ok=list.reduce((n,[,d])=>n+d.ok,0),bad=list.reduce((n,[,d])=>n+d.bad,0);
  root.setAttribute('aria-label',ok+' envios feitos e '+bad+' com problema nos últimos '+list.length+' dias com registro');
  for(const [ref,d] of list){
   const col=el('div','col'),stack=el('div','stack');
   if(d.bad){const seg=el('div','seg bad');seg.style.height=(d.bad/max*100)+'%';seg.title=day(ref)+': '+d.bad+' com problema';stack.append(seg);}
   if(d.ok){const seg=el('div','seg ok');seg.style.height=(d.ok/max*100)+'%';seg.title=day(ref)+': '+d.ok+' enviado'+(d.ok===1?'':'s');stack.append(seg);}
   col.append(stack,el('div','day',day(ref).slice(0,5)));root.append(col);
  }
 }
 function renderOverview(){
  if(!$('kpis'))return;
  const rows=groupRows(),waLabel=connected?'Conectado':connection?'Desconectado':'Sem conexão';
  const ativos=botgroups.filter(botOn).length+watches.filter(itemOn).length+subscriptions.filter(itemOn).length;
  $('nav-rotinas').textContent=subscriptions.length||'';$('nav-alertas').textContent=watches.length||'';$('nav-comandos').textContent=botgroups.length||'';
  $('top-wa').textContent='WhatsApp: '+waLabel;$('top-wa').className='chip'+(connected?' on':'');
  const kpis=$('kpis');kpis.replaceChildren(
   kpi('WhatsApp',waLabel,connected?groups.length+' grupos disponíveis':'Veja a aba WhatsApp',connected?'good':'bad'),
   kpi('Grupos com bot',rows.length,rows.length?'com comandos, alerta ou bom dia':'nenhum bot configurado ainda'),
   kpi('Bots ativos',ativos,'comandos + alertas + rotinas ligados',ativos?'good':''),
   meterKpi('Comandos',botgroups.length,3),meterKpi('Alertas',watches.length,3),meterKpi('Rotinas de bom dia',subscriptions.length,5));
  const query=$('ov-search').value.trim().toLowerCase();
  const visible=rows.filter(r=>(!query||r.grupo.toLowerCase().includes(query))&&(filtro==='todos'||(filtro==='ativos'&&(botOn(r.comandos)||itemOn(r.alerta)||itemOn(r.bomdia)))||(filtro==='pausados'&&((r.comandos&&!botOn(r.comandos))||(r.alerta&&!itemOn(r.alerta))||(r.bomdia&&!itemOn(r.bomdia))))||(filtro==='sem'&&!r.bomdia)));
  const root=$('ov-groups');root.replaceChildren();
  if(!rows.length)root.append(el('p','muted','Nenhum bot configurado ainda. Use as abas Bom dia, Alertas e Comandos para criar o primeiro.'));
  else if(!visible.length)root.append(el('p','muted','Nenhum grupo corresponde ao filtro.'));
  for(const r of visible)root.append(groupCard(r));
  activity();
 }
 document.querySelectorAll('.tabbtn[data-tab]').forEach(b=>{b.onclick=()=>goTab(b.dataset.tab);});
 document.querySelectorAll('#ov-filters [data-filter]').forEach(b=>{b.onclick=()=>{filtro=b.dataset.filter;document.querySelectorAll('#ov-filters [data-filter]').forEach(x=>x.classList.toggle('on',x===b));renderOverview();};});
 $('ov-search').oninput=renderOverview;$('top-wa').onclick=()=>goTab('conexao');
 $('refresh-all').onclick=guarded(async()=>{await refresh();await loadRoutines();await loadWatches().catch(()=>{});await loadBotgroups().catch(()=>{});notice('Painel atualizado.');});
 // as listas se atualizam sozinhas a cada minuto (sem mexer em um formulário aberto)
 setInterval(()=>{if(closed||!connection||document.hidden||!$('editor').hidden)return;Promise.all([loadRoutines(),loadWatches(),loadBotgroups()]).catch(()=>{});},60000);
 $('new-routine').onclick=()=>openEditor(null);$('editor-cancel').onclick=closeEditor;
 $('group-search').oninput=()=>renderGroups();
 $('preview').onclick=guarded(async()=>showPreview(await api('preview','POST',collect())));
 $('save').onclick=guarded(()=>saveRoutine(false));$('activate').onclick=guarded(()=>saveRoutine(true));
 $('pair').onclick=guarded(async()=>{if(!$('risk').checked)throw Error('Aceite os riscos antes de conectar.');if(!connection)connection=(await api('connections','POST',{riskAccepted:true})).id;await api('connections/'+connection+'/pair','POST');await refresh();});
 $('refresh').onclick=guarded(async()=>{await refresh();await loadRoutines();});
 $('revoke').onclick=guarded(async()=>{if(connection)await api('connections/'+connection,'DELETE');connection='';clearQR();await refresh();await loadRoutines();notice('Conexão revogada e agendas suspensas.');});
 $('runs').onclick=guarded(async()=>{runs=await api('runs');renderRuns(runs,'Todo o histórico');});
 $('close-preview').onclick=()=>{$('preview-card').hidden=true;};$('close-runs').onclick=()=>{$('runs-card').hidden=true;};
 $('logout').onclick=logout;window.addEventListener('pagehide',logout);
 async function boot(){
  if(!window.pywebview?.api){notice('Abra esta janela pelo aplicativo instalado.');return;}
  const c=await window.pywebview.api.boot();if(closed)return;if(c.error){notice(c.error);return;}
  mode=c.mode;configurationData=c.config&&typeof c.config==='object'&&!Array.isArray(c.config)?c.config:{};$('settings').hidden=false;
  const live=mode!=='simulation';$('mode').textContent=live?'Envio real':'Simulação';$('mode').className='badge '+(live?'good':'warn');
  $('mode').title=live?'Integração não oficial — envios reais exigem sua conexão e rotina ativa.':'Modo de simulação — sem envio real.';
  $('activate').textContent=live?'Salvar e ativar':'Salvar e ativar simulação';
  await refresh();await loadRoutines();await loadWatches().catch(()=>{});await loadBotgroups().catch(()=>{});if(closed)return;goTab('geral');notice('');
 }
 $('reveal-recovery').onclick=guarded(async()=>{clearRecovery();const epoch=recoveryEpoch;const r=await window.pywebview.api.reveal_recovery();if(closed||epoch!==recoveryEpoch)return;if(r.error)throw Error(r.error);$('recovery-code').textContent=r.code;recoveryTimer=setTimeout(clearRecovery,30000);});
 $('recovery-input').oninput=()=>{clearTimeout(recoveryTimer);recoveryTimer=setTimeout(clearRecovery,30000);};
 $('recover').onclick=guarded(async()=>{const code=$('recovery-input').value.trim();clearRecovery();const r=await window.pywebview.api.recover(code);if(r.error)throw Error(r.error);await boot();notice('Acesso recuperado. O código anterior foi invalidado. Guarde seu novo código se precisar.');});
 let started=false;const start=()=>{if(started)return;started=true;boot().catch(()=>notice('Gestão indisponível. Tente novamente.'));};
 window.addEventListener('pywebviewready',start);if(window.pywebview?.api)start();
})();
