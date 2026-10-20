(function(){
'use strict';
const el=id=>document.getElementById(id), page=el('page-voz');
if(!page)return;
const nomes={local:'Local Chat',log:'Server Log',up:'UP Level',death:'Death',help:'Help',ia:'Tudo IA'};
const fixos=['local','log','ia'], defaults=['local','log','up','death','help','ia'], chave='zt-assistente-canais-v1';
let abertos=[...defaults], atual='ia', dadosMonitor={personagens:[],up:[],death:[]}, monitorBusy=false, monitorLendo=false, monitorVersion=0, ultimaMonitor='', first=true;
const naoLidos={up:0,death:0}, conhecidos={up:new Set(),death:new Set()};
try{const salvo=JSON.parse(localStorage.getItem(chave));if(salvo&&Array.isArray(salvo.abertos)&&salvo.abertos.every(id=>Object.hasOwn(nomes,id))){abertos=[...new Set([...fixos.slice(0,2),...salvo.abertos.filter(id=>!fixos.includes(id)),'ia'])];if(abertos.includes(salvo.atual))atual=salvo.atual;}}catch(e){/* Preferência indisponível: usa os canais padrão. */}
const card=page.querySelector('.chat'), barra=page.querySelector('.chat-canais'), tabs={}, paineis={};
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const button=(text,fn)=>{const b=node('button',text);b.type='button';b.addEventListener('click',fn);return b;};
const guardar=()=>{try{localStorage.setItem(chave,JSON.stringify({abertos,atual}));}catch(e){/* A sessão continua sem persistência. */}};
for(const id of ['local','log','help','ia'])tabs[id]=el('chat-canal-'+id);
for(const id of ['up','death']){const p=node('section',undefined,'monitor-feed');p.id='assistente-painel-'+id;p.setAttribute('role','tabpanel');p.setAttribute('aria-labelledby','chat-canal-'+id);p.setAttribute('aria-live','polite');paineis[id]=p;card.insertBefore(p,el('chat-grip'));}
const row=node('div',undefined,'assistente-canais-linha'), scroll=node('div',undefined,'assistente-canais-scroll');barra.before(row);row.append(scroll);scroll.append(barra);
const abrirBotao=button('Abrir canal',()=>abrirDialog());abrirBotao.id='assistente-canal-abrir';row.append(abrirBotao);
function desenharTabs(){
 barra.replaceChildren();
 for(const id of abertos){
  const wrap=node('span',undefined,'assistente-aba');let tab=tabs[id];
  if(!tab){tab=tabs[id]=button(nomes[id],()=>selecionar(id));tab.id='chat-canal-'+id;tab.setAttribute('role','tab');}
  tab.textContent=nomes[id]+(naoLidos[id]?' ('+naoLidos[id]+')':'');
  tab.setAttribute('aria-selected',String(id===atual));tab.tabIndex=id===atual?0:-1;
  tab.setAttribute('aria-controls',paineis[id]?.id||(id==='help'?'assistente-instrucoes':'chat-mensagens'));
  wrap.append(tab);
  if(!fixos.includes(id)){const close=button('×',()=>fechar(id));close.className='assistente-aba-fechar';close.setAttribute('aria-label','Fechar canal '+nomes[id]);wrap.append(close);}
  barra.append(wrap);
 }
 const ia=barra.lastElementChild;ia.classList.add('assistente-aba-ia');
}
function restaurar(){
 for(const [id,panel] of Object.entries(paineis))panel.hidden=id!==atual;
 const conversa=['local','log','ia'].includes(atual);
 el('chat-mensagens').hidden=!conversa;el('assistente-instrucoes').hidden=atual!=='help';
 el('chat-form').hidden=!['local','ia'].includes(atual);
 el('chat-canal-ajuda').hidden=!['local','log','help','ia'].includes(atual);
 if(!conversa)el('chat-digitando').hidden=true;
 for(const id of abertos){tabs[id].setAttribute('aria-selected',String(id===atual));tabs[id].tabIndex=id===atual?0:-1;}
}
function selecionar(id){
 if(!abertos.includes(id)||!Object.hasOwn(nomes,id))return;
 atual=id;if(Object.hasOwn(naoLidos,id))naoLidos[id]=0;
 desenharTabs();
 if(['local','log','help','ia'].includes(id)&&window.chatSelecionar)window.chatSelecionar(id);
 restaurar();guardar();
 if(id!=='ia'){
  const rect=tabs[id].parentElement.getBoundingClientRect(),left=scroll.getBoundingClientRect().left,
   right=barra.lastElementChild.getBoundingClientRect().left;
  if(rect.left<left)scroll.scrollLeft+=rect.left-left-3;
  else if(rect.right>right)scroll.scrollLeft+=rect.right-right+3;
 }
}
function abrir(id){if(!Object.hasOwn(nomes,id))return;if(!abertos.includes(id))abertos.splice(abertos.length-1,0,id);selecionar(id);}
function fechar(id){if(fixos.includes(id)||!abertos.includes(id))return;abertos=abertos.filter(x=>x!==id);if(atual===id)atual='ia';selecionar(atual);tabs[atual]?.focus();}
barra.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)||event.target.getAttribute('role')!=='tab')return;event.preventDefault();const i=abertos.indexOf(atual),n=event.key==='Home'?0:event.key==='End'?abertos.length-1:(i+(event.key==='ArrowRight'?1:abertos.length-1))%abertos.length;selecionar(abertos[n]);tabs[atual].focus();});
function dialog(id,title){const d=node('dialog',undefined,'assistente-dialog');d.id=id;const h=node('h2',title);h.id=id+'-titulo';d.setAttribute('aria-labelledby',h.id);d.append(h);page.append(d);return d;}
const canalDialog=dialog('assistente-canal-dialog','Abrir canal'), lista=node('select');lista.id='assistente-canal-lista';lista.size=9;lista.setAttribute('aria-label','Canais disponíveis');for(const [id,title] of Object.entries(nomes)){if(fixos.includes(id))continue;const option=node('option',title);option.value=id;lista.append(option);}canalDialog.append(lista);
function escolher(){canalEscolhido=!!lista.value;if(lista.value)abrir(lista.value);canalDialog.close();}
const canalAcoes=node('div',undefined,'assistente-dialog-acoes');canalAcoes.append(button('Abrir',escolher),button('Cancelar',()=>canalDialog.close()));canalDialog.append(canalAcoes);
lista.addEventListener('dblclick',escolher);lista.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();escolher();}});
function abrirDialog(){lista.value='up';canalDialog.showModal();lista.focus();}
let canalEscolhido=false;
canalDialog.addEventListener('close',()=>{if(canalEscolhido){tabs[atual]?.focus();canalEscolhido=false;}else abrirBotao.focus();});
const monitorPanel=el('character-track');
monitorPanel.append(node('p','A primeira leitura cria a referência sem avisos antigos. UP usa a lista online do mundo (consulta a cada 60 s; cache da fonte de 60 s). Death usa a ficha (intervalo mínimo de 60 s por personagem; cache de até 5 min). Com muitos personagens, o ciclo fica maior. Esses atrasos podem se somar. Funciona com o aplicativo aberto, inclusive minimizado.','dica'));
const individual=node('div',undefined,'card calmo'),form=node('form',undefined,'monitor-adicionar'),nome=node('input');nome.id='assistente-monitor-nome';nome.maxLength=40;nome.required=true;nome.placeholder='Nome do personagem';nome.setAttribute('aria-label','Nome do personagem');const adicionar=node('button','Adicionar personagem','btn btn-primary');adicionar.type='submit';form.append(nome,adicionar);individual.append(form);
const meus=node('select');meus.id='assistente-monitor-meus';meus.setAttribute('aria-label','Adicionar dos meus personagens');const meusBtn=button('Adicionar dos meus personagens',()=>alterar(meus.value,true,true));meusBtn.className='btn btn-sm';individual.append(meus,meusBtn);monitorPanel.append(individual);
const guildCard=node('div',undefined,'card calmo'),guildForm=node('form',undefined,'monitor-adicionar'),guildNome=node('input');guildNome.id='track-guild-name';guildNome.maxLength=100;guildNome.required=true;guildNome.placeholder='Nome da guild';guildNome.setAttribute('aria-label','Nome da guild');const guildSearch=node('button','Buscar guild','btn btn-sm');guildForm.append(guildNome,guildSearch);guildCard.append(node('h3','Adicionar uma guild inteira'),guildForm);
const guildStatus=node('p');guildStatus.id='track-guild-status';guildStatus.setAttribute('role','status');const guildOptions=node('div',undefined,'track-guild-options'),guildUp=node('input'),guildDeath=node('input');guildUp.type=guildDeath.type='checkbox';guildUp.id='track-guild-up';guildDeath.id='track-guild-death';guildUp.checked=guildDeath.checked=true;
for(const [input,title] of [[guildUp,'UP Level'],[guildDeath,'Death']]){const label=node('label');label.append(input,document.createTextNode(title));guildOptions.append(label);}const guildImport=button('Adicionar membros',importGuild);guildImport.id='track-guild-import';guildImport.className='btn btn-primary';guildImport.disabled=true;guildCard.append(guildStatus,guildOptions,node('p','As opções são aplicadas só aos novos membros. Personagens já cadastrados mantêm suas opções e referências. A importação usa a lista encontrada agora; não sincroniza entradas ou saídas automaticamente.','dica'),guildImport);const workload=node('p');workload.id='track-workload';workload.className='dica';guildCard.append(workload);monitorPanel.append(guildCard);
const aviso=node('p');aviso.id='assistente-monitor-status';aviso.setAttribute('role','status');const filter=node('input');filter.id='track-filter';filter.placeholder='Filtrar personagens';filter.setAttribute('aria-label','Filtrar personagens');const count=node('p');count.id='track-count';const listaMonitor=node('div');listaMonitor.id='assistente-monitor-lista';monitorPanel.append(aviso,filter,count,node('p','Notificação de UP envia um aviso do Windows. Som de UP toca um sinal adicional do aplicativo; o Windows pode tocar seu próprio som. Os avisos exigem UP Level ligado e o aplicativo aberto, inclusive minimizado.','dica'),listaMonitor);
let guildPreview=null,guildVersion=0,guildImportBusy=false;const monitorRows=new Map();
function fillMeus(){const old=meus.value;meus.replaceChildren();for(const p of typeof MEUS!=='undefined'?MEUS.lista||[]:[]){const o=node('option',p.nome);o.value=p.nome;meus.append(o);}if([...meus.options].some(o=>o.value===old))meus.value=old;meusBtn.disabled=!meus.children.length;}
page.querySelector('[data-assistente-tab="character-track"]').addEventListener('click',()=>{fillMeus();renderMonitor();});fillMeus();
form.addEventListener('submit',e=>{e.preventDefault();alterar(nome.value,true,true);});filter.addEventListener('input',renderMonitor);
guildNome.addEventListener('input',()=>{++guildVersion;guildPreview=null;guildImport.disabled=true;guildStatus.textContent='';renderGuildSummary();});
guildUp.addEventListener('change',renderGuildSummary);guildDeath.addEventListener('change',renderGuildSummary);
guildForm.addEventListener('submit',async e=>{e.preventDefault();const version=++guildVersion,name=guildNome.value.trim();guildPreview=null;guildImport.disabled=true;guildStatus.textContent='Consultando a lista de membros…';try{const result=await window.pywebview.api.assistente_monitor_guild(name);if(version!==guildVersion)return;if(result.erro)throw Error(result.erro);if(!Array.isArray(result.members))throw Error('Lista de membros indisponível.');guildPreview=result;renderGuildSummary();}catch(error){if(version===guildVersion)guildStatus.textContent=error.message||'Não foi possível consultar a guild.';}});
function renderGuildSummary(){const members=dadosMonitor.personagens||[],existing=new Set(members.map(p=>p.nome.toLowerCase()));let incoming=0;if(guildPreview){incoming=guildPreview.members.filter(p=>!existing.has(p.nome.toLowerCase())).length;guildStatus.textContent=`${guildPreview.guild} · ${guildPreview.world} · ${guildPreview.total} membros: ${incoming} novos e ${guildPreview.total-incoming} já cadastrados. ${guildPreview.velho?'Dados anteriores da fonte. ':''}${guildPreview.consulta?'Consulta: '+new Date(guildPreview.consulta*1000).toLocaleString('pt-BR')+'. ':''}${guildPreview.fonte||''}`;}guildImport.disabled=!guildPreview||!incoming||guildImportBusy;const deathCount=members.filter(p=>p.death).length+(guildDeath.checked?incoming:0);workload.textContent=`UP compartilha uma consulta por mundo. Death consulta uma ficha por personagem: ${deathCount} com Death${guildPreview?' após adicionar os novos':''}. Mínimo aproximado de ${deathCount} s para iniciar essas consultas, sem contar respostas e pausas. Ciclo mínimo aproximado: ${Math.max(60,deathCount)} s, podendo ser maior por respostas, outras consultas e pausas; o cache da ficha também pode atrasar até 5 min.`;}
async function importGuild(){if(!guildPreview||monitorBusy)return;const preview=guildPreview,up=guildUp.checked,death=guildDeath.checked;monitorBusy=true;guildImportBusy=true;++monitorVersion;renderGuildSummary();aviso.textContent='Adicionando membros…';try{const data=await window.pywebview.api.assistente_monitor_importar(preview.members,up,death);if(data.erro)throw Error(data.erro);dadosMonitor=data;const result=data.importacao;aviso.textContent=result?`${result.adicionados} adicionados; ${result.existentes} já cadastrados e preservados.`:'Importação concluída.';renderMonitor();renderFeeds();}catch(error){aviso.textContent=error.message||'Não foi possível importar. Nenhuma alteração confirmada.';}finally{monitorBusy=false;guildImportBusy=false;renderGuildSummary();}}
async function alterar(name,up,death,remove=false,notifyWindows,notifySound){if(monitorBusy){aviso.textContent='Aguarde o cadastro atual terminar.';return;}if(!name)return;monitorBusy=true;++monitorVersion;aviso.textContent='Salvando…';try{const current=(dadosMonitor.personagens||[]).find(p=>p.nome.toLowerCase()===name.toLowerCase());const data=await window.pywebview.api.assistente_monitor_configurar(name,up,death,remove,notifyWindows??current?.notify_windows??false,notifySound??current?.notify_sound??false);if(data.erro)throw new Error(data.erro);dadosMonitor=data;nome.value='';aviso.textContent='Monitoramento salvo.';renderMonitor();renderFeeds();}catch(e){aviso.textContent=e.message||'Não foi possível salvar.';}finally{monitorBusy=false;}}
function renderMonitor(){
 const rows=dadosMonitor.personagens||[],names=new Set(rows.map(p=>p.nome.toLowerCase())),query=filter.value.trim().toLowerCase(),checked=value=>value?new Date(value*1000).toLocaleString('pt-BR'):'ainda não';
 for(const [key,row] of monitorRows)if(!names.has(key)){row.root.remove();monitorRows.delete(key);}
 let visible=0;for(const p of rows){const key=p.nome.toLowerCase();let row=monitorRows.get(key);if(!row){row={root:node('div',undefined,'monitor-personagem'),name:node('strong'),status:node('small'),last:node('small'),source:node('small')};row.root.append(row.name);for(const [field,title] of [['up','UP Level'],['death','Death'],['notify_windows','Notificação de UP'],['notify_sound','Som de UP']]){const label=node('label'),input=node('input');input.type='checkbox';input.setAttribute('aria-label',title+' de '+p.nome);input.addEventListener('change',()=>{const current=(dadosMonitor.personagens||[]).find(v=>v.nome.toLowerCase()===key);if(!current)return;if(monitorBusy){input.checked=current[field];return;}const next={up:current.up,death:current.death,notify_windows:current.notify_windows===true,notify_sound:current.notify_sound===true};next[field]=input.checked;alterar(current.nome,next.up,next.death,false,next.notify_windows,next.notify_sound);});row[field]=input;label.append(input,document.createTextNode(title));row.root.append(label);}const remove=button('Remover',()=>{const current=(dadosMonitor.personagens||[]).find(v=>v.nome.toLowerCase()===key);if(current)alterar(current.nome,current.up,current.death,true);});remove.setAttribute('aria-label','Remover '+p.nome);row.root.append(remove,row.status,row.last,row.source);monitorRows.set(key,row);listaMonitor.append(row.root);}
 const texts=[[row.name,p.nome],[row.status,p.estado||'Aguardando consulta'],[row.last,`Última verificação — UP: ${checked(p.ultima_verificacao_up)} · Death: ${checked(p.ultima_verificacao_death)}`],[row.source,`Fonte UP: lista online de ${p.world||'mundo a descobrir'} (60 s) · Death: ficha (até 5 min).`]];for(const [n,text] of texts)if(n.textContent!==text)n.textContent=text;for(const field of ['up','death','notify_windows','notify_sound'])row[field].checked=p[field]===true;row.root.hidden=!!query&&!key.includes(query);if(!row.root.hidden)visible++;}
 count.textContent=rows.length?`${visible} de ${rows.length} personagens · limite de 1000.`:'Nenhum personagem monitorado. Cadastre até 1000.';renderGuildSummary();
}
function renderFeeds(){for(const channel of ['up','death']){const out=paineis[channel];out.replaceChildren();for(const event of dadosMonitor[channel]||[]){const row=node('p'),at=new Date(event.at);row.textContent=(Number.isNaN(at.getTime())?'':at.toLocaleString('pt-BR')+' · ')+event.texto;out.append(row);}if(!out.children.length)out.append(node('p','Nenhum evento registrado. Cadastre personagens em Monitoramento.'));out.scrollTop=out.scrollHeight;}}
function canalVisivel(channel){return atual===channel&&!document.hidden&&page.classList.contains('shown')&&!page.querySelector('[data-assistente-panel=overview]').hidden;}
function marcarLidos(){if(Object.hasOwn(naoLidos,atual)&&naoLidos[atual]&&canalVisivel(atual)){naoLidos[atual]=0;desenharTabs();}}
async function refreshMonitor(){
 if(monitorBusy||monitorLendo||!window.pywebview?.api?.assistente_monitor_estado)return;
 monitorLendo=true;const version=monitorVersion;
 try{const data=await window.pywebview.api.assistente_monitor_estado();if(version!==monitorVersion)return;if(data.erro)throw new Error(data.erro);for(const channel of ['up','death']){const events=data[channel]||[];for(const event of events){if(!first&&!conhecidos[channel].has(event.id)&&!canalVisivel(channel))naoLidos[channel]++;}conhecidos[channel]=new Set(events.map(event=>event.id));}first=false;const sig=JSON.stringify(data);dadosMonitor=data;if(sig!==ultimaMonitor){ultimaMonitor=sig;renderFeeds();renderMonitor();desenharTabs();}aviso.textContent=[data.aviso,data.aviso_rede].filter(Boolean).join(' ');}catch(e){if(version===monitorVersion)aviso.textContent='Monitoramento indisponível agora.';}finally{monitorLendo=false;}
}
window.assistenteCanais={abrir,selecionar,fechar,restaurar,visivel:marcarLidos,atual:()=>atual,area:()=>paineis[atual]||(atual==='help'?el('assistente-instrucoes'):el('chat-mensagens')),refreshMonitor};
document.addEventListener('visibilitychange',marcarLidos);new MutationObserver(marcarLidos).observe(page,{attributes:true,subtree:true,attributeFilter:['class','hidden']});
desenharTabs();selecionar(atual);window.addEventListener('pywebviewready',refreshMonitor);refreshMonitor();setInterval(refreshMonitor,1000);
})();
