// Menu "Mensagens" (as mensagens automáticas do WhatsApp). Recurso fechado: o menu só aparece nas instalações liberadas;
// rotinas, alertas, comandos e conexão ficam na janela de gestão. A liberação vem de um código de acesso (Configurações).
function maKey(r){return 'zt-mensagem-automatica-v1:'+JSON.stringify([r.personagem||'',r.mundo||''].map(v=>String(v).trim().toLowerCase()));}
// Preferências salvas antes da tela única só preenchem a "Nova rotina".
function maSaved(r){try{const v=JSON.parse(localStorage.getItem(maKey(r))||'{}');return v&&typeof v==='object'&&!Array.isArray(v)?v:{};}catch(e){return {};}}
async function maAtualizar(){
 try{
  if(typeof api?.recursos_liberados!=='function')return;
  const r=await api.recursos_liberados();
  const menu=document.getElementById('mensagens-menu');if(menu)menu.hidden=r.mensagens_automaticas!==true;
  // o menu Admin se mostra sozinho: o app só informa "liberado" quando o arquivo de liberação existe
  if(typeof window.adminIaCarregar==='function')window.adminIaCarregar();
 }catch(e){/* sem a ponte do app (ou falha): o menu fica escondido */}
}
async function maAbrir(){
 const status=document.getElementById('ma-status');
 try{
  if(typeof api?.mensagem_automatica_abrir_portal!=='function')throw Error();
  let contexto={};try{contexto=(await api.assistente_estado()).context||{};}catch(e){/* abre mesmo sem personagem */}
  const r={personagem:contexto.character_id||'',mundo:contexto.world_id||''};
  const result=await api.mensagem_automatica_abrir_portal({...maSaved(r),...r});
  status.textContent=result.erro||'';
 }catch(e){status.textContent='Não foi possível abrir as mensagens automáticas.';}
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
 const abrir=document.getElementById('ma-abrir'),ok=document.getElementById('cfg-codigo-ok');
 if(abrir)abrir.onclick=maAbrir;
 if(ok)ok.onclick=maAtivarCodigo;
 maAtualizar();
}
if(typeof window!=='undefined'&&window.addEventListener){window.addEventListener('pywebviewready',maIniciar);}
if(typeof document!=='undefined'&&document.getElementById)maIniciar();
