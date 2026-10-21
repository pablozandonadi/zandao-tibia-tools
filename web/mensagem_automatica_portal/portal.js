'use strict';
// Credencial somente em memória; nenhuma configuração ou token vai para a URL.
(()=>{
 const $=id=>document.getElementById(id);
 let connection='',connected=false,groups=[],subscriptions=[],runs=[],editing=null,mode='simulation',qrTimer,configurationData=null,recoveryTimer,recoveryEpoch=0,closed=false,armed='';
 const BLOCKS=[['dia','Data'],['saudacao','Saudação'],['frase','Mensagem do dia'],['mundo','Mundo'],['calendario','Eventos do Tibia'],['yasir','Yasir (consulta online)'],['rashid','Rashid'],['criatura','Criatura boostada'],['boss','Boss boostado'],['dream','Dream Court'],['dream_mortes','Dream Court — mortes (Last Day)'],['mudancas_online','Outras world changes (consulta online)'],['server_save','Próximo SS']];
 const FIELDS=[['comunidade','Comunidade'],['assinatura','Assinatura'],['deeplings','Boss Deeplings'],['regiao','Região boostada'],['roshamuul','Roshamuul / robôs'],['drome','Tibia Drome (fim da rotação)'],['coin_compra','TC: comprar (gp)'],['coin_venda','TC: vender (gp)'],['coin_hora','Horário dos preços']];
 const EXTRAS=[['kill','Top 10 criaturas mortas ontem','mundo'],['exp_mundo','Top 10 XP do servidor (ontem)','mundo'],['exp_guild','Top XP da guild (ontem)','guild'],['guild','Resumo da guild','guild'],['online_guild','Online da guild','guild'],['char','Personagem (ficha e mortes recentes)','personagem'],['transfer','Entraram e saíram do mundo (10 dias)','mundo']];
 const NEW_BLOCKS=['dia','saudacao','frase','mundo','server_save'];
 const notice=text=>$('notice').textContent=text;
 const clearQR=()=>{clearTimeout(qrTimer);$('qr').hidden=true;$('qr').removeAttribute('src');};
 function clearRecovery(){recoveryEpoch++;clearTimeout(recoveryTimer);$('recovery-code').textContent='';$('recovery-input').value='';}
 function logout(){closed=true;$('access-controls').hidden=true;clearQR();clearRecovery();connection='';groups=[];subscriptions=[];runs=[];editing=null;configurationData=null;$('routines').replaceChildren();$('settings').hidden=true;notice('Gestão encerrada. Feche esta janela.');}
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
  $('runs-card').hidden=false;$('runs-title').textContent=title;const root=$('runs-result');root.replaceChildren();
  if(!items.length)root.append(el('p','muted','Nenhuma execução registrada.'));
  else{const list=document.createElement('ul');for(const item of items)list.append(el('li','',day(item.reference)+' · '+stateLabel(item.state)));root.append(list);}
  $('runs-card').scrollIntoView({block:'nearest'});
 }
 function showPreview(r){$('preview-card').hidden=false;$('preview-result').textContent=r.text;$('preview-card').scrollIntoView({block:'nearest'});notice('Prévia gerada. Nenhum envio realizado.');}
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
 function openEditor(s){
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
  for(const [k,label,kind] of EXTRAS){const row=el('div','row');tick(row,'extras',k,label,on('extras',k));row.append(field('arg',k,val('args',k,40),40,'Padrão: '+(kind==='guild'?'guild do personagem':kind==='mundo'?'mundo acima':'personagem acima'),label+': outro '+kind+' (opcional)'));extras.append(row);}
  $('group-search').value='';renderGroups(s?.destinationLabel);
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
 async function loadRoutines(){[subscriptions,runs]=await Promise.all([api('subscriptions'),api('runs')]);renderRoutines();}
 function renderRoutines(){
  const root=$('routines');root.replaceChildren();$('routine-count').textContent=subscriptions.length+' de 5';
  if(!subscriptions.length){root.append(el('p','muted','Nenhuma rotina ainda. Clique em "+ Nova rotina".'));return;}
  for(const s of subscriptions){
   const c=s.config||{},on=s.state==='active',name=text(s.destinationLabel)||'Grupo sem nome',last=runs.find(r=>r.subscription===s.id&&(r.state==='accepted'||r.state==='simulated'));
   const card=el('article','routine'+(on?' on':'')),head=el('div','routine-head');
   head.append(el('span','badge '+(on?'good':''),stateLabel(s.state)),el('h3','',name));
   card.append(head,el('p','',schedule(c)),el('p','muted',(text(c.personagem)||'Sem personagem')+' · '+(text(c.mundo)||'Sem mundo')),el('p','muted','Último envio: '+(last?day(last.reference)+' · '+stateLabel(last.state):'nenhum ainda')));
   const actions=el('div','actions');
   const add=(label,fn,className)=>{const b=el('button',className,label);b.type='button';b.onclick=guarded(()=>fn(b));actions.append(b);};
   add('Editar',async()=>openEditor(s),'primary');
   add(on?'Pausar':'Ativar',async()=>{await api('subscriptions/'+s.id,'PUT',routineBody(s,s.config,!on));await loadRoutines();notice(on?'Rotina pausada.':'Rotina ativada.');});
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
 function setConnection(label,tone,detail){const b=$('connection-state');b.textContent=label;b.className='badge '+tone;$('connection-detail').textContent=detail;$('pair-box').hidden=connected;$('revoke').hidden=!connection;}
 async function refresh(){
  clearQR();const list=await api('connections');const current=list.find(c=>c.state!=='revoked');connection=current?.id||'';connected=false;groups=[];renderGroups();
  if(!connection){setConnection('Desconectado','bad','Nenhuma conexão ativa. Aceite os riscos e conecte seu WhatsApp.');return;}
  const status=await api('connections/'+connection);connected=status.state==='connected';
  setConnection((mode==='simulation'?'Simulação · ':'')+stateLabel(status.state),connected?'good':status.state==='pairing'?'warn':'bad',connected?'':'Escaneie o QR no celular: WhatsApp › Aparelhos conectados.');
  if(status.qrImage&&status.expiresAt>Date.now()/1000&&/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(status.qrImage)){
   $('qr').src=status.qrImage;$('qr').hidden=false;qrTimer=setTimeout(clearQR,Math.min((status.expiresAt-Date.now()/1000)*1000,90000));
  }
  if(connected){groups=await api('connections/'+connection+'/groups');renderGroups(editing?.destinationLabel);$('connection-detail').textContent=groups.length+' grupos disponíveis para envio.';}
 }
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
  await refresh();await loadRoutines();if(closed)return;notice('');
 }
 $('reveal-recovery').onclick=guarded(async()=>{clearRecovery();const epoch=recoveryEpoch;const r=await window.pywebview.api.reveal_recovery();if(closed||epoch!==recoveryEpoch)return;if(r.error)throw Error(r.error);$('recovery-code').textContent=r.code;recoveryTimer=setTimeout(clearRecovery,30000);});
 $('recovery-input').oninput=()=>{clearTimeout(recoveryTimer);recoveryTimer=setTimeout(clearRecovery,30000);};
 $('recover').onclick=guarded(async()=>{const code=$('recovery-input').value.trim();clearRecovery();const r=await window.pywebview.api.recover(code);if(r.error)throw Error(r.error);await boot();notice('Acesso recuperado. O código anterior foi invalidado. Guarde seu novo código se precisar.');});
 let started=false;const start=()=>{if(started)return;started=true;boot().catch(()=>notice('Gestão indisponível. Tente novamente.'));};
 window.addEventListener('pywebviewready',start);if(window.pywebview?.api)start();
})();
