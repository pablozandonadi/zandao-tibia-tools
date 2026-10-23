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
function maIniciar(){
 const ok=document.getElementById('cfg-codigo-ok');
 if(ok)ok.onclick=maAtivarCodigo;
 maAtualizar();
}
if(typeof window!=='undefined'&&window.addEventListener){window.addEventListener('pywebviewready',maIniciar);}
if(typeof document!=='undefined'&&document.getElementById)maIniciar();
