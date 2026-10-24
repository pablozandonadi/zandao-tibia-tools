// Menu "Mensagens" (as mensagens automáticas do WhatsApp). Recurso fechado: o menu só aparece nas instalações liberadas e,
// ao clicar, abre direto a janela de gestão (rotinas, alertas, comandos e conexão). A liberação vem de um código de acesso (Configurações).
function maKey(r){return 'zt-mensagem-automatica-v1:'+JSON.stringify([r.personagem||'',r.mundo||''].map(v=>String(v).trim().toLowerCase()));}
// Preferências salvas antes da tela única só preenchem a "Nova rotina".
function maSaved(r){try{const v=JSON.parse(localStorage.getItem(maKey(r))||'{}');return v&&typeof v==='object'&&!Array.isArray(v)?v:{};}catch(e){return {};}}
function maAviso(texto,erro){try{if(typeof toast==='function')toast(texto,erro);}catch(e){/* sem aviso na tela */}}
async function maAtualizar(){
 try{
  if(typeof api?.recursos_liberados!=='function')return;
  const r=await api.recursos_liberados();
  const menu=document.getElementById('mensagens-menu');if(menu)menu.hidden=r.mensagens_automaticas!==true;
  // o menu Admin se mostra sozinho: o app só informa "liberado" quando o arquivo de liberação existe
  if(typeof window.adminIaCarregar==='function')window.adminIaCarregar();
 }catch(e){/* sem a ponte do app (ou falha): o menu fica escondido */}
}
let maAbrindo=false;
async function maAbrir(){
 if(maAbrindo)return;maAbrindo=true;
 try{
  if(typeof api?.mensagem_automatica_abrir_portal!=='function')throw Error();
  let contexto={};try{contexto=(await api.assistente_estado()).context||{};}catch(e){/* abre mesmo sem personagem */}
  const r={personagem:contexto.character_id||'',mundo:contexto.world_id||''};
  const result=await api.mensagem_automatica_abrir_portal({...maSaved(r),...r});
  if(result&&result.erro)maAviso(result.erro,true);
 }catch(e){maAviso('Não foi possível abrir as mensagens automáticas.',true);}
 finally{setTimeout(()=>{maAbrindo=false;},1500);}  // um clique só: evita abrir várias janelas
}
async function maAtivarCodigo(){
 const campo=document.getElementById('cfg-codigo'),status=document.getElementById('cfg-codigo-status'),botao=document.getElementById('cfg-codigo-ok');
 const codigo=campo.value.trim();if(!codigo){status.textContent='Cole o código de acesso.';return;}
 botao.disabled=true;status.textContent='Verificando…';
 try{
  const r=await api.liberar_recursos(codigo);
  if(r.erro){status.textContent=r.erro;return;}
  campo.value='';status.textContent='Código aceito. Os recursos liberados já aparecem no menu.';await maAtualizar();
 }catch(e){status.textContent='Não foi possível ativar agora. Tente de novo em instantes.';}
 finally{botao.disabled=false;}
}
// ---- Painel dentro da janela principal: onde cada bot está rodando, grupo por grupo (todo texto entra por textContent) ----
function maH(tag,props,...filhos){
 const e=document.createElement(tag),{texto,...resto}=props||{};
 if(texto!==undefined)e.textContent=texto;
 Object.assign(e,resto);e.append(...filhos.filter(Boolean));return e;  // filhos nulos (ex.: sem origem) não viram o texto "null"
}
const MA_FUSOS={'America/Sao_Paulo':'Brasília','America/Cuiaba':'Cuiabá','America/Manaus':'Manaus','America/Rio_Branco':'Rio Branco','America/Noronha':'Noronha'};
const maQuando=epoch=>epoch?new Date(epoch*1000).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'nunca';
const maDuracao=s=>s>=3600&&s%3600===0?s/3600+' h':s>=60&&s%60===0?s/60+' min':s+' s';
const maEstado=(ligado,rotulo)=>maH('span',{className:'pilula'+(ligado?' on':''),texto:rotulo});
function maCelula(...linhas){const c=maH('td',{style:'vertical-align:top;padding:8px'});linhas.filter(Boolean).forEach(l=>c.append(typeof l==='string'?maH('div',{texto:l}):l));return c;}
function maOrigem(o){return o&&(o.origem==='grupo'||o.ajustadoPeloGrupo)?maH('span',{className:'dica',texto:o.origem==='grupo'?' · criado pelo grupo':' · ajustado pelo grupo'}):null;}
function maCelulaComandos(c){
 if(!c)return maCelula('—');
 const ligado=c.estado==='active'&&!c.pausado;
 return maCelula(maH('div',{style:'margin-bottom:6px'},maEstado(ligado,c.pausado?'pausado pelo grupo':ligado?'ativo':'pausado'),maOrigem(c)),
  `Mundo ${c.mundo||'?'} · 1 comando a cada ${c.intervalo?maDuracao(c.intervalo):'?'}`,c.desligados.length?'Desligados aqui: '+c.desligados.join(', '):'',
  'Último uso: '+maQuando(c.ultimoUso),c.configPeloGrupo?'':'Configuração pelo grupo bloqueada');
}
function maCelulaAlerta(a){
 if(!a)return maCelula('—');
 return maCelula(maH('div',{style:'margin-bottom:6px'},maEstado(a.estado==='active',a.estado==='active'?'ativo':'pausado'),maOrigem(a)),`Guild ${a.guild||'?'}`,
  `${a.level===1?'Todo level up':'Level up a cada '+a.level}${a.mortes?' · mortes':''}${a.ups?'':' · sem level up'}`,
  `${a.limiteHora===0?'Sem limite por hora':'Até '+a.limiteHora+' por hora'} · até ${a.limiteMinuto} por minuto`,'Último aviso: '+maQuando(a.ultimoEnvio));
}
function maCelulaBomDia(b){
 if(!b)return maCelula('—');
 const dia=b.ultimoEnvio?b.ultimoEnvio.split('-').reverse().join('/'):'nunca';
 return maCelula(maH('div',{style:'margin-bottom:6px'},maEstado(b.estado==='active',b.estado==='active'?'ligado':'pausado'),maOrigem(b)),`Envio às ${b.envio||'?'}${b.fuso?' ('+(MA_FUSOS[b.fuso]||b.fuso.split('/').pop().replace('_',' '))+')':''} · mundo ${b.mundo||'?'}`,'Último envio: '+dia);
}
function maDesenhar(d){
 const resumo=document.getElementById('ma-resumo'),painel=document.getElementById('ma-painel'),aviso=document.getElementById('ma-aviso');
 if(!resumo||!painel)return;
 if(!d||d.erro){resumo.replaceChildren();painel.replaceChildren();if(aviso)aviso.textContent=(d&&d.erro)||'Não foi possível carregar o painel.';return;}
 if(aviso)aviso.textContent='';
 const rotulo={connected:'WhatsApp conectado',disconnected:'WhatsApp desconectado',pairing:'Aguardando o QR do WhatsApp',desconectado:'WhatsApp desconectado',revoked:'WhatsApp desconectado'};
 const r=d.resumo;
 resumo.replaceChildren(maEstado(d.conexao.estado==='connected',(rotulo[d.conexao.estado]||'WhatsApp: '+d.conexao.estado)+(d.conexao.simulado?' (simulação)':'')),
  maH('span',{className:'pilula',texto:`${r.grupos} grupo${r.grupos===1?'':'s'}`}),maH('span',{className:'pilula',texto:`${r.botsAtivos} bot${r.botsAtivos===1?'':'s'} ativo${r.botsAtivos===1?'':'s'}`}),
  maH('span',{className:'pilula',texto:`Comandos ${r.comandos[0]}/${r.comandos[1]}`}),maH('span',{className:'pilula',texto:`Alertas ${r.alertas[0]}/${r.alertas[1]}`}),maH('span',{className:'pilula',texto:`Rotinas ${r.rotinas[0]}/${r.rotinas[1]}`}));
 if(!d.grupos.length){painel.replaceChildren(maH('p',{className:'dica',texto:'Nenhum bot configurado ainda. Abra o editor para conectar o WhatsApp e criar o primeiro.'}));return;}
 painel.replaceChildren(maH('table',{className:'tabela-itens'},maH('thead',{},maH('tr',{},...['Grupo','Comandos','Alerta da guild','Bom dia'].map(t=>maH('th',{texto:t,style:'text-align:left'})))),
  maH('tbody',{},...d.grupos.map(g=>maH('tr',{},maH('td',{style:'vertical-align:top;padding:8px'},maH('strong',{texto:g.grupo})),maCelulaComandos(g.comandos),maCelulaAlerta(g.alerta),maCelulaBomDia(g.bomdia))))));
}
let maPainelGeracao=0,maTimer=null;
async function maPainelCarregar(){
 if(typeof api?.mensagens_painel!=='function')return;
 const g=++maPainelGeracao,aviso=document.getElementById('ma-aviso');
 if(aviso)aviso.textContent='Carregando…';
 let d;try{d=await api.mensagens_painel();}catch(e){d={erro:'Não foi possível carregar o painel agora.'};}
 if(g===maPainelGeracao)maDesenhar(d);
}
function maIniciar(){
 const ok=document.getElementById('cfg-codigo-ok');
 if(ok)ok.onclick=maAtivarCodigo;
 const atualizar=document.getElementById('ma-atualizar'),editor=document.getElementById('ma-editor');
 if(atualizar)atualizar.onclick=maPainelCarregar;
 if(editor)editor.onclick=maAbrir;
 // enquanto a página está aberta, o painel se atualiza sozinho
 if(!maTimer&&typeof setInterval==='function')maTimer=setInterval(()=>{const p=document.getElementById('page-mensagens');if(p&&p.classList&&p.classList.contains('shown'))maPainelCarregar();},60000);
 maAtualizar();
}
if(typeof window!=='undefined'&&window.addEventListener){window.addEventListener('pywebviewready',maIniciar);}
if(typeof document!=='undefined'&&document.getElementById)maIniciar();
