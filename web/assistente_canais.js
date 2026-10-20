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
const monitorDialog=dialog('assistente-monitor-dialog','Monitoramento de personagens');
monitorDialog.append(node('p','A primeira leitura cria a referência sem avisos antigos. UP usa a lista online do mundo (consulta a cada 60 s; cache da fonte de 60 s). Death usa a ficha (consulta a cada 60 s; cache da fonte de até 5 min). Esses atrasos podem se somar. Funciona com o aplicativo aberto, inclusive minimizado.'));
const form=node('form',undefined,'monitor-adicionar'), nome=node('input');nome.id='assistente-monitor-nome';nome.maxLength=40;nome.required=true;nome.placeholder='Nome do personagem';nome.setAttribute('aria-label','Nome do personagem');const adicionar=node('button','Adicionar');adicionar.type='submit';form.append(nome,adicionar);monitorDialog.append(form);
const meus=node('select');meus.id='assistente-monitor-meus';meus.setAttribute('aria-label','Adicionar dos meus personagens');const meusBtn=button('Adicionar dos meus personagens',()=>alterar(meus.value,true,true));monitorDialog.append(meus,meusBtn);
const aviso=node('p');aviso.id='assistente-monitor-status';aviso.setAttribute('role','status');const listaMonitor=node('div');listaMonitor.id='assistente-monitor-lista';monitorDialog.append(aviso,listaMonitor,button('Fechar',()=>monitorDialog.close()));
el('assistente-monitor-abrir').addEventListener('click',()=>{meus.replaceChildren();for(const p of typeof MEUS!=='undefined'?MEUS.lista||[]:[]){const o=node('option',p.nome);o.value=p.nome;meus.append(o);}meusBtn.disabled=!meus.children.length;monitorDialog.showModal();renderMonitor();nome.focus();});
monitorDialog.addEventListener('close',()=>el('assistente-monitor-abrir').focus());
form.addEventListener('submit',e=>{e.preventDefault();alterar(nome.value,true,true);});
async function alterar(name,up,death,remove=false){if(monitorBusy){aviso.textContent='Aguarde o cadastro atual terminar.';return;}if(!name)return;monitorBusy=true;++monitorVersion;aviso.textContent='Salvando…';try{const data=await window.pywebview.api.assistente_monitor_configurar(name,up,death,remove);if(data.erro)throw new Error(data.erro);dadosMonitor=data;nome.value='';aviso.textContent='Monitoramento salvo.';renderMonitor();renderFeeds();}catch(e){aviso.textContent=e.message||'Não foi possível salvar.';}finally{monitorBusy=false;}}
function renderMonitor(){
 listaMonitor.replaceChildren();
 const checked=value=>value?new Date(value*1000).toLocaleString('pt-BR'):'ainda não';
 for(const p of dadosMonitor.personagens||[]){const row=node('div',undefined,'monitor-personagem');row.append(node('strong',p.nome));for(const [key,title] of [['up','UP Level'],['death','Death']]){const label=node('label'),input=node('input');input.type='checkbox';input.checked=p[key];input.addEventListener('change',()=>{if(monitorBusy){input.checked=p[key];return;}alterar(p.nome,key==='up'?input.checked:p.up,key==='death'?input.checked:p.death);});label.append(input,document.createTextNode(title));row.append(label);}row.append(button('Remover',()=>alterar(p.nome,p.up,p.death,true)),node('small',p.estado||'Aguardando consulta'),node('small',`Última verificação — UP: ${checked(p.ultima_verificacao_up)} · Death: ${checked(p.ultima_verificacao_death)}`),node('small',`Fonte UP: lista online de ${p.world||'mundo a descobrir'} (60 s) · Death: ficha (até 5 min).`));listaMonitor.append(row);}
 if(!dadosMonitor.personagens?.length)listaMonitor.append(node('p','Nenhum personagem monitorado. Cadastre até 20.'));
}
function renderFeeds(){for(const channel of ['up','death']){const out=paineis[channel];out.replaceChildren();for(const event of dadosMonitor[channel]||[]){const row=node('p'),at=new Date(event.at);row.textContent=(Number.isNaN(at.getTime())?'':at.toLocaleString('pt-BR')+' · ')+event.texto;out.append(row);}if(!out.children.length)out.append(node('p','Nenhum evento registrado. Cadastre personagens em Monitoramento.'));out.scrollTop=out.scrollHeight;}}
function canalVisivel(channel){return atual===channel&&!document.hidden&&page.classList.contains('shown')&&!page.querySelector('[data-assistente-panel=overview]').hidden;}
function marcarLidos(){if(Object.hasOwn(naoLidos,atual)&&naoLidos[atual]&&canalVisivel(atual)){naoLidos[atual]=0;desenharTabs();}}
async function refreshMonitor(){
 if(monitorBusy||monitorLendo||!window.pywebview?.api?.assistente_monitor_estado)return;
 monitorLendo=true;const version=monitorVersion;
 try{const data=await window.pywebview.api.assistente_monitor_estado();if(version!==monitorVersion)return;if(data.erro)throw new Error(data.erro);for(const channel of ['up','death']){const events=data[channel]||[];for(const event of events){if(!first&&!conhecidos[channel].has(event.id)&&!canalVisivel(channel))naoLidos[channel]++;}conhecidos[channel]=new Set(events.map(event=>event.id));}first=false;const sig=JSON.stringify(data);dadosMonitor=data;if(sig!==ultimaMonitor){ultimaMonitor=sig;renderFeeds();if(monitorDialog.open)renderMonitor();desenharTabs();}aviso.textContent=[data.aviso,data.aviso_rede].filter(Boolean).join(' ');}catch(e){if(version===monitorVersion)aviso.textContent='Monitoramento indisponível agora.';}finally{monitorLendo=false;}
}
window.assistenteCanais={abrir,selecionar,fechar,restaurar,visivel:marcarLidos,atual:()=>atual,area:()=>paineis[atual]||(atual==='help'?el('assistente-instrucoes'):el('chat-mensagens')),refreshMonitor};
document.addEventListener('visibilitychange',marcarLidos);new MutationObserver(marcarLidos).observe(page,{attributes:true,subtree:true,attributeFilter:['class','hidden']});
desenharTabs();selecionar(atual);window.addEventListener('pywebviewready',refreshMonitor);refreshMonitor();setInterval(refreshMonitor,1000);
})();
