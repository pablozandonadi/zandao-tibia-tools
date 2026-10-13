(() => {
const init = () => {
 const dialog=document.getElementById('apoio-dialog');
 document.getElementById('cafe-apoio').addEventListener('click',()=>dialog.showModal());
 document.getElementById('apoio-fechar').addEventListener('click',()=>dialog.close());
 const status=document.getElementById('apoio-status');
 document.getElementById('apoio-copiar').addEventListener('click',async()=>{
  const field=document.getElementById('apoio-pix');
  try { await navigator.clipboard.writeText(field.value); status.textContent='Pix copiado. Cole no aplicativo do seu banco.'; }
  catch { field.focus();field.select(); status.textContent=document.execCommand('copy')?'Pix copiado.':'Selecione o código e pressione Ctrl+C para copiar.'; }
 });
 document.querySelectorAll('.nav-item').forEach(item=>item.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();item.click();}}));
 const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
 document.querySelectorAll('[data-animated-src]').forEach(img=>{
  const owner=img.closest('button')||img.parentElement;
  const play=()=>{if(!reduced.matches)img.src=img.dataset.animatedSrc;};
  const stop=()=>{img.src=img.dataset.staticSrc;};
  owner.addEventListener('mouseenter',play);owner.addEventListener('mouseleave',stop);
  owner.addEventListener('focusin',play);owner.addEventListener('focusout',stop);
 });
};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
