'use strict';
// Credencial somente em memória; nenhuma configuração ou token vai para a URL.
(()=>{
 const $=id=>document.getElementById(id);
 let connection='',subscriptions=[],mode='simulation',qrTimer,configurationData=null,recoveryTimer,recoveryEpoch=0,closed=false;
 const notice=text=>$('notice').textContent=text;
 const clearQR=()=>{clearTimeout(qrTimer);$('qr').hidden=true;$('qr').removeAttribute('src');};
 function clearRecovery(){recoveryEpoch++;clearTimeout(recoveryTimer);$('recovery-code').textContent='';$('recovery-input').value='';}
 function logout(){closed=true;$('access-controls').hidden=true;clearQR();clearRecovery();connection='';subscriptions=[];configurationData=null;$('settings').hidden=true;notice('Gestão encerrada. Feche esta janela.');}
 async function api(path,method='GET',body){
  const result=await window.pywebview.api.request('/v1/'+path,method,body||null);
  if(result.error)throw Error(result.error);return result.data;
 }
 const guarded=fn=>async()=>{try{await fn();}catch(e){notice(e.message||'Falha na operação.');}};
 const labels={dia:'Data',saudacao:'Saudação',frase:'Mensagem do dia',mundo:'Mundo',calendario:'Eventos do Tibia',yasir:'Yasir',rashid:'Rashid',criatura:'Criatura boostada',boss:'Boss boostado',dream:'Dream Court',dream_mortes:'Dream Court — mortes',mudancas_online:'Outras world changes online',server_save:'Próximo SS',comunidade:'Comunidade',assinatura:'Assinatura',deeplings:'Boss Deeplings',regiao:'Região boostada',roshamuul:'Roshamuul / robôs',drome:'Tibia Drome',coin_compra:'TC: comprar (gp)',coin_venda:'TC: vender (gp)',coin_hora:'Horário dos preços',kill:'Criaturas mortas ontem',exp_mundo:'XP do servidor',exp_guild:'XP da guild',guild:'Resumo da guild',online_guild:'Online da guild',char:'Personagem',transfer:'Entraram e saíram do mundo'};
 const stateLabel=state=>({active:'Ativa',inactive:'Pausada',connected:'Conectado',disconnected:'Desconectado',pairing:'Aguardando pareamento',revoked:'Revogada',pending:'Aguardando geração',preparing:'Gerando',ready:'Aguardando horário de envio',sending:'Envio em andamento',simulated:'Simulado — sem envio',accepted:'Aceito pelo WhatsApp — leitura não confirmada',uncertain:'Resultado incerto — não reenviar sem conferir',expired:'Expirado',cancelled:'Cancelado',failed:'Não concluído'})[state]||'Situação indisponível';
 const text=value=>typeof value==='string'?value.slice(0,200):'';
 function setConfig(c){
  if(!c||Array.isArray(c)||typeof c!=='object')throw Error('Escolha um arquivo de configuração válido.');
  configurationData=c;const root=$('config-summary');root.replaceChildren();const title=document.createElement('h2');title.textContent='Sua mensagem';root.append(title);
  const line=(label,value)=>{const p=document.createElement('p');const b=document.createElement('strong');b.textContent=label+': ';p.append(b,document.createTextNode(value));root.append(p);};
  line('Personagem',text(c.personagem)||'Não informado');line('Mundo',text(c.mundo)||'Não informado');line('Gerar às',text(c.generateAt)||'Não definido');line('Enviar às',text(c.sendAt)||'Não definido');line('Fuso horário',text(c.timezone)||'Não definido');
  const selected=group=>Object.entries(group&&typeof group==='object'?group:{}).filter(([k,v])=>v===true&&labels[k]).map(([k])=>k);
  line('Conteúdo',selected(c.blocks).map(k=>labels[k]).join(', ')||'Nenhum bloco selecionado');
  for(const key of selected(c.fields))line(labels[key],text(c.values?.[key])||'Valor não informado');
  if(selected(c.fields).length)line('Data dos valores manuais',text(c.manualDate)||'Não informada');
  for(const key of selected(c.extras))line(labels[key],text(c.args?.[key])||'Padrão do personagem e mundo acima');
 }
 function renderRuns(items){
  const root=$('runs-result');root.replaceChildren();const title=document.createElement('h2');title.textContent='Execuções recentes';root.append(title);
  if(!items.length){const p=document.createElement('p');p.textContent='Nenhuma execução registrada.';root.append(p);return;}
  const list=document.createElement('ul');for(const item of items){const row=document.createElement('li'),date=/^\d{4}-\d{2}-\d{2}$/.test(item.reference||'')?item.reference.split('-').reverse().join('/'):'Data indisponível';row.textContent=date+' · '+stateLabel(item.state);list.append(row);}root.append(list);
 }
 const configuration=()=>{if(!configurationData)throw Error('Importe um arquivo de configuração válido.');return structuredClone(configurationData);};
 function options(element,items,first){element.replaceChildren(new Option(first,''));for(const item of items)element.add(new Option(item.label||item.id,item.id));}
 async function loadSubscriptions(){subscriptions=await api('subscriptions');options($('subscriptions'),subscriptions.map(s=>({id:s.id,label:s.config.personagem+' · '+s.config.mundo+' · '+stateLabel(s.state)})),'Nova configuração');}
 async function refresh(){
  clearQR();const list=await api('connections');const current=list.find(c=>c.state!=='revoked');connection=current?.id||'';
  options($('groups'),[],'Escolha um grupo');if(!connection){$('connection-state').textContent='Nenhuma conexão ativa.';return;}
  const status=await api('connections/'+connection);$('connection-state').textContent=(mode==='simulation'?'Simulação · ':'')+stateLabel(status.state);
  if(status.qrImage&&status.expiresAt>Date.now()/1000&&/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(status.qrImage)){
   $('qr').src=status.qrImage;$('qr').hidden=false;qrTimer=setTimeout(clearQR,Math.min((status.expiresAt-Date.now()/1000)*1000,90000));
  }
  if(status.state==='connected')options($('groups'),await api('connections/'+connection+'/groups'),'Escolha um grupo');
 }
 async function save(active){
  if(!connection||!$('groups').value)throw Error('Conecte sua conta e escolha o grupo.');
  const config=configuration();const dest=await api('destinations','POST',{connection,group:$('groups').value});
  const selected=$('subscriptions').value;const body={config,connection,destination:dest.id,active};
  const result=await api('subscriptions'+(selected?'/'+selected:''),selected?'PUT':'POST',body);
  await loadSubscriptions();$('subscriptions').value=result.id;
  notice(mode==='simulation'?(active?'Agenda de simulação ativada. Nenhuma mensagem real será enviada.':'Configuração de simulação salva e pausada.'):(active?'Agenda ativada para sua conexão e grupo selecionados.':'Configuração salva e pausada.'));
 }
 $('import').onchange=guarded(async()=>{const file=$('import').files[0];if(!file||file.size>32768)throw Error('Escolha um JSON de até 32 KB.');const c=JSON.parse(await file.text());setConfig(c);notice('Configuração importada. Revise e gere uma prévia antes de salvar.');});
 $('preview').onclick=guarded(async()=>{const r=await api('preview','POST',configuration());$('preview-result').textContent=r.text+'\n\nDados de referência: '+r.reference_date;notice('Prévia gerada. Nenhum envio realizado.');});
 $('pair').onclick=guarded(async()=>{if(!$('risk').checked)throw Error('Aceite os riscos antes de conectar.');if(!connection)connection=(await api('connections','POST',{riskAccepted:true})).id;await api('connections/'+connection+'/pair','POST');await refresh();});
 $('refresh').onclick=guarded(refresh);
 $('revoke').onclick=guarded(async()=>{if(connection)await api('connections/'+connection,'DELETE');connection='';clearQR();await refresh();await loadSubscriptions();notice('Conexão revogada e agendas suspensas.');});
 $('save').onclick=guarded(()=>save(false));$('activate').onclick=guarded(()=>save(true));
 $('pause').onclick=guarded(async()=>{const s=subscriptions.find(s=>s.id===$('subscriptions').value);if(!s)throw Error('Escolha uma configuração salva.');await api('subscriptions/'+s.id,'PUT',{config:s.config,connection:s.connection,destination:s.destination,active:false});await loadSubscriptions();notice('Agenda pausada.');});
 $('subscriptions').onchange=()=>{const s=subscriptions.find(s=>s.id===$('subscriptions').value);if(s){setConfig(s.config);connection=s.connection;}};
 $('runs').onclick=guarded(async()=>{renderRuns(await api('runs'));});
 $('logout').onclick=logout;window.addEventListener('pagehide',logout);
 async function boot(){
  if(!window.pywebview?.api){notice('Abra esta janela pelo aplicativo instalado.');return;}
  const c=await window.pywebview.api.boot();if(closed)return;if(c.error){notice(c.error);return;}
  mode=c.mode;setConfig(c.config);$('settings').hidden=false;
  $('mode').textContent=mode==='simulation'?'Modo de simulação — sem envio real.':'Integração não oficial — envios reais exigem sua conexão e agenda ativa.';
  $('activate').textContent=mode==='simulation'?'Ativar agenda de simulação':'Ativar agenda';
  await loadSubscriptions();await refresh();if(closed)return;notice('Sua configuração está pronta para revisar. Salvar não ativa o envio.');
 }
 $('reveal-recovery').onclick=guarded(async()=>{clearRecovery();const epoch=recoveryEpoch;const r=await window.pywebview.api.reveal_recovery();if(closed||epoch!==recoveryEpoch)return;if(r.error)throw Error(r.error);$('recovery-code').textContent=r.code;recoveryTimer=setTimeout(clearRecovery,30000);});
 $('recovery-input').oninput=()=>{clearTimeout(recoveryTimer);recoveryTimer=setTimeout(clearRecovery,30000);};
 $('recover').onclick=guarded(async()=>{const code=$('recovery-input').value.trim();clearRecovery();const r=await window.pywebview.api.recover(code);if(r.error)throw Error(r.error);await boot();notice('Acesso recuperado. O código anterior foi invalidado. Guarde seu novo código se precisar.');});
 let started=false;const start=()=>{if(started)return;started=true;boot().catch(()=>notice('Gestão indisponível. Tente novamente.'));};
 window.addEventListener('pywebviewready',start);if(window.pywebview?.api)start();
})();
