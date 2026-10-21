// Atalho para a tela de mensagens automáticas; rotinas, conteúdo e horários são geridos lá.
function maKey(r){return 'zt-mensagem-automatica-v1:'+JSON.stringify([r.personagem||'',r.mundo||''].map(v=>String(v).trim().toLowerCase()));}
// Preferências salvas antes da tela única só preenchem a "Nova rotina".
function maSaved(r){try{const v=JSON.parse(localStorage.getItem(maKey(r))||'{}');return v&&typeof v==='object'&&!Array.isArray(v)?v:{};}catch(e){return {};}}
function maPanel(r){
 return `<div class="ma-panel"><p><strong>Mensagens automáticas</strong></p><p class="zb-muted">Envie a mensagem do dia sozinha no WhatsApp, no horário que escolher, mesmo com o PC desligado. Rotinas, conteúdo, horários e conexão ficam todos na mesma tela.</p><button type="button" data-ma-portal>Abrir mensagens automáticas</button><p data-ma-status role="status" aria-live="polite"></p></div>`;
}
function maBind(r){
 const panel=document.querySelector('.ma-panel');if(!panel)return;
 panel.querySelector('[data-ma-portal]').onclick=async()=>{
  const status=panel.querySelector('[data-ma-status]');
  try{if(typeof api?.mensagem_automatica_abrir_portal!=='function')throw Error();const result=await api.mensagem_automatica_abrir_portal({...maSaved(r),personagem:r.personagem||'',mundo:r.mundo||''});status.textContent=result.erro||'';}
  catch(e){status.textContent='Não foi possível abrir as mensagens automáticas.';}
 };
}
