'use strict';
// Credencial somente em memória; nenhuma configuração ou token vai para a URL.
(()=>{
 const $=id=>document.getElementById(id);
 let connection='',connected=false,subscriptions=[],runs=[],mode='simulation',qrTimer,configurationData=null,recoveryTimer,recoveryEpoch=0,closed=false,armed='';
 const notice=text=>$('notice').textContent=text;
 const clearQR=()=>{clearTimeout(qrTimer);$('qr').hidden=true;$('qr').removeAttribute('src');};
 function clearRecovery(){recoveryEpoch++;clearTimeout(recoveryTimer);$('recovery-code').textContent='';$('recovery-input').value='';}
 function logout(){closed=true;$('access-controls').hidden=true;clearQR();clearRecovery();connection='';subscriptions=[];runs=[];configurationData=null;$('routines').replaceChildren();$('settings').hidden=true;notice('Gestão encerrada. Feche esta janela.');}
 async function api(path,method='GET',body){
  const result=await window.pywebview.api.request('/v1/'+path,method,body||null);
  if(result.error)throw Error(result.error);return result.data;
 }
 const guarded=fn=>async()=>{try{await fn();}catch(e){notice(e.message||'Falha na operação.');}};
 const labels={dia:'Data',saudacao:'Saudação',frase:'Mensagem do dia',mundo:'Mundo',calendario:'Eventos do Tibia',yasir:'Yasir',rashid:'Rashid',criatura:'Criatura boostada',boss:'Boss boostado',dream:'Dream Court',dream_mortes:'Dream Court — mortes',mudancas_online:'Outras world changes online',server_save:'Próximo SS',comunidade:'Comunidade',assinatura:'Assinatura',deeplings:'Boss Deeplings',regiao:'Região boostada',roshamuul:'Roshamuul / robôs',drome:'Tibia Drome',coin_compra:'TC: comprar (gp)',coin_venda:'TC: vender (gp)',coin_hora:'Horário dos preços',kill:'Criaturas mortas ontem',exp_mundo:'XP do servidor',exp_guild:'XP da guild',guild:'Resumo da guild',online_guild:'Online da guild',char:'Personagem',transfer:'Entraram e saíram do mundo'};
 const stateLabel=state=>({active:'Ativa',inactive:'Pausada',connected:'Conectado',disconnected:'Desconectado',pairing:'Aguardando pareamento',revoked:'Revogada',pending:'Aguardando geração',preparing:'Gerando',ready:'Aguardando horário de envio',sending:'Envio em andamento',simulated:'Simulado — sem envio',accepted:'Aceito pelo WhatsApp — leitura não confirmada',uncertain:'Resultado incerto — não reenviar sem conferir',expired:'Expirado',cancelled:'Cancelado',failed:'Não concluído'})[state]||'Situação indisponível';
 const text=value=>typeof value==='string'?value.slice(0,200):'';
 const el=(tag,className,content)=>{const e=document.createElement(tag);if(className)e.className=className;if(content!==undefined)e.textContent=content;return e;};
 const day=ref=>/^\d{4}-\d{2}-\d{2}$/.test(ref||'')?ref.split('-').reverse().join('/'):'Data indisponível';
 const schedule=c=>c.generateAt&&c.sendAt?'Gera '+text(c.generateAt)+' · Envia '+text(c.sendAt)+' · '+(text(c.timezone)||'sem fuso'):'Sem horário definido';
 function setConfig(c){
  if(!c||Array.isArray(c)||typeof c!=='object')throw Error('Escolha um arquivo de configuração válido.');
  configurationData=c;const root=$('config-summary');root.replaceChildren();
  const line=(label,value)=>{const p=document.createElement('p');const b=document.createElement('strong');b.textContent=label+': ';p.append(b,document.createTextNode(value));root.append(p);};
  line('Personagem',text(c.personagem)||'Não informado');line('Mundo',text(c.mundo)||'Não informado');line('Gerar às',text(c.generateAt)||'Não definido');line('Enviar às',text(c.sendAt)||'Não definido');line('Fuso horário',text(c.timezone)||'Não definido');
  const selected=group=>Object.entries(group&&typeof group==='object'?group:{}).filter(([k,v])=>v===true&&labels[k]).map(([k])=>k);
  line('Conteúdo',selected(c.blocks).map(k=>labels[k]).join(', ')||'Nenhum bloco selecionado');
  for(const key of selected(c.fields))line(labels[key],text(c.values?.[key])||'Valor não informado');
  if(selected(c.fields).length)line('Data dos valores manuais',text(c.manualDate)||'Não informada');
  for(const key of selected(c.extras))line(labels[key],text(c.args?.[key])||'Padrão do personagem e mundo acima');
 }
 function renderRuns(items,title){
  $('runs-card').hidden=false;$('runs-title').textContent=title;const root=$('runs-result');root.replaceChildren();
  if(!items.length)root.append(el('p','muted','Nenhuma execução registrada.'));
  else{const list=document.createElement('ul');for(const item of items)list.append(el('li','',day(item.reference)+' · '+stateLabel(item.state)));root.append(list);}
  $('runs-card').scrollIntoView({block:'nearest'});
 }
 function showPreview(r){$('preview-card').hidden=false;$('preview-result').textContent=r.text;$('preview-card').scrollIntoView({block:'nearest'});notice('Prévia gerada. Nenhum envio realizado.');}
 const configuration=()=>{if(!configurationData)throw Error('Importe um arquivo de configuração válido.');return structuredClone(configurationData);};
 function options(element,items,first){element.replaceChildren(new Option(first,''));for(const item of items)element.add(new Option(item.label||item.id,item.id));}
 const routineBody=(s,config,active)=>({config,connection:s.connection,destination:s.destination,active});
 async function loadRoutines(){[subscriptions,runs]=await Promise.all([api('subscriptions'),api('runs')]);renderRoutines();}
 function renderRoutines(){
  const root=$('routines');root.replaceChildren();$('routine-count').textContent=subscriptions.length+' de 5';
  if(!subscriptions.length){root.append(el('p','muted','Nenhuma rotina ainda. Crie uma em "Nova rotina".'));return;}
  for(const s of subscriptions){
   const c=s.config||{},on=s.state==='active',name=text(s.destinationLabel)||'Grupo sem nome',last=runs.find(r=>r.subscription===s.id&&(r.state==='accepted'||r.state==='simulated'));
   const card=el('article','routine'+(on?' on':'')),head=el('div','routine-head');
   head.append(el('span','badge '+(on?'good':''),stateLabel(s.state)),el('h3','',name));
   card.append(head,el('p','',schedule(c)),el('p','muted',(text(c.personagem)||'Sem personagem')+' · '+(text(c.mundo)||'Sem mundo')),el('p','muted','Último envio: '+(last?day(last.reference)+' · '+stateLabel(last.state):'nenhum ainda')));
   const actions=el('div','actions');
   const add=(label,fn,className)=>{const b=el('button',className,label);b.type='button';b.onclick=guarded(()=>fn(b));actions.append(b);};
   add(on?'Pausar':'Ativar',async()=>{await api('subscriptions/'+s.id,'PUT',routineBody(s,s.config,!on));await loadRoutines();notice(on?'Rotina pausada.':'Rotina ativada.');},on?'':'primary');
   add('Atualizar com o app',async()=>{const config=configuration();await api('subscriptions/'+s.id,'PUT',routineBody(s,config,on));await loadRoutines();notice('Rotina atualizada com a configuração do app: '+schedule(config)+'.');});
   add('Prévia',async()=>showPreview(await api('preview','POST',s.config)));
   add('Histórico',async()=>renderRuns(runs.filter(r=>r.subscription===s.id),'Histórico · '+name));
   // Exclusão em dois cliques: o primeiro só arma por 5 segundos.
   add('Excluir',async b=>{
    if(armed!==s.id){armed=s.id;b.textContent='Confirmar exclusão';setTimeout(()=>{if(armed===s.id){armed='';b.textContent='Excluir';}},5000);return;}
    armed='';await api('subscriptions/'+s.id,'DELETE');await loadRoutines();notice('Rotina excluída.');
   },'danger');
   card.append(actions);root.append(card);
  }
 }
 function setConnection(label,tone,detail){const b=$('connection-state');b.textContent=label;b.className='badge '+tone;$('connection-detail').textContent=detail;$('pair-box').hidden=connected;$('revoke').hidden=!connection;}
 async function refresh(){
  clearQR();const list=await api('connections');const current=list.find(c=>c.state!=='revoked');connection=current?.id||'';connected=false;
  options($('groups'),[],'Escolha um grupo');
  if(!connection){setConnection('Desconectado','bad','Nenhuma conexão ativa. Aceite os riscos e conecte seu WhatsApp.');return;}
  const status=await api('connections/'+connection);connected=status.state==='connected';
  setConnection((mode==='simulation'?'Simulação · ':'')+stateLabel(status.state),connected?'good':status.state==='pairing'?'warn':'bad',connected?'':'Escaneie o QR no celular: WhatsApp › Aparelhos conectados.');
  if(status.qrImage&&status.expiresAt>Date.now()/1000&&/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(status.qrImage)){
   $('qr').src=status.qrImage;$('qr').hidden=false;qrTimer=setTimeout(clearQR,Math.min((status.expiresAt-Date.now()/1000)*1000,90000));
  }
  if(connected){const groups=await api('connections/'+connection+'/groups');options($('groups'),groups,'Escolha um grupo');$('connection-detail').textContent=groups.length+' grupos disponíveis para envio.';}
 }
 async function create(active){
  if(!connection||!$('groups').value)throw Error('Conecte sua conta e escolha o grupo.');
  const config=configuration();const dest=await api('destinations','POST',{connection,group:$('groups').value});
  await api('subscriptions','POST',{config,connection,destination:dest.id,active});await loadRoutines();
  notice(mode==='simulation'?(active?'Agenda de simulação ativada. Nenhuma mensagem real será enviada.':'Configuração de simulação salva e pausada.'):(active?'Rotina criada e ativada.':'Rotina criada e pausada.'));
 }
 $('import').onchange=guarded(async()=>{const file=$('import').files[0];if(!file||file.size>32768)throw Error('Escolha um JSON de até 32 KB.');const c=JSON.parse(await file.text());setConfig(c);notice('Configuração importada. Revise e gere uma prévia antes de salvar.');});
 $('preview').onclick=guarded(async()=>showPreview(await api('preview','POST',configuration())));
 $('pair').onclick=guarded(async()=>{if(!$('risk').checked)throw Error('Aceite os riscos antes de conectar.');if(!connection)connection=(await api('connections','POST',{riskAccepted:true})).id;await api('connections/'+connection+'/pair','POST');await refresh();});
 $('refresh').onclick=guarded(async()=>{await refresh();await loadRoutines();});
 $('revoke').onclick=guarded(async()=>{if(connection)await api('connections/'+connection,'DELETE');connection='';clearQR();await refresh();await loadRoutines();notice('Conexão revogada e agendas suspensas.');});
 $('save').onclick=guarded(()=>create(false));$('activate').onclick=guarded(()=>create(true));
 $('runs').onclick=guarded(async()=>{runs=await api('runs');renderRuns(runs,'Todo o histórico');});
 $('close-preview').onclick=()=>{$('preview-card').hidden=true;};$('close-runs').onclick=()=>{$('runs-card').hidden=true;};
 $('logout').onclick=logout;window.addEventListener('pagehide',logout);
 async function boot(){
  if(!window.pywebview?.api){notice('Abra esta janela pelo aplicativo instalado.');return;}
  const c=await window.pywebview.api.boot();if(closed)return;if(c.error){notice(c.error);return;}
  mode=c.mode;setConfig(c.config);$('settings').hidden=false;
  const live=mode!=='simulation';$('mode').textContent=live?'Envio real':'Simulação';$('mode').className='badge '+(live?'good':'warn');
  $('mode').title=live?'Integração não oficial — envios reais exigem sua conexão e rotina ativa.':'Modo de simulação — sem envio real.';
  $('activate').textContent=live?'Criar e ativar':'Criar e ativar simulação';
  await refresh();await loadRoutines();if(closed)return;notice('');
 }
 $('reveal-recovery').onclick=guarded(async()=>{clearRecovery();const epoch=recoveryEpoch;const r=await window.pywebview.api.reveal_recovery();if(closed||epoch!==recoveryEpoch)return;if(r.error)throw Error(r.error);$('recovery-code').textContent=r.code;recoveryTimer=setTimeout(clearRecovery,30000);});
 $('recovery-input').oninput=()=>{clearTimeout(recoveryTimer);recoveryTimer=setTimeout(clearRecovery,30000);};
 $('recover').onclick=guarded(async()=>{const code=$('recovery-input').value.trim();clearRecovery();const r=await window.pywebview.api.recover(code);if(r.error)throw Error(r.error);await boot();notice('Acesso recuperado. O código anterior foi invalidado. Guarde seu novo código se precisar.');});
 let started=false;const start=()=>{if(started)return;started=true;boot().catch(()=>notice('Gestão indisponível. Tente novamente.'));};
 window.addEventListener('pywebviewready',start);if(window.pywebview?.api)start();
})();
