let tiResult=null,tiRequest=0,tiPasteTimer=null;
const tiNum=n=>Number(n).toLocaleString('pt-BR');
function tiHtml(r){
  if(r.erro)return `<p class="dica">${esc(r.erro)}</p>`;
  const labels={tasks:'Itens de task',imbuements:'Itens de embuimentos',other:'Outros itens dropados'};
  return `<p class="dica">${tiNum(r.total)} itens · ${r.distinct} tipos · catálogo de tasks: ${esc(r.catalog_date)}</p>`+Object.entries(labels).map(([key,label])=>`<section class="card calmo ti-section"><h2 class="sub">${label} (${r.groups[key].length})</h2><div class="ti-grid">${r.groups[key].map(i=>`<article class="ti-card" tabindex="0" role="button" aria-label="Copiar nome: ${esc(i.name)}" data-ti-name="${esc(i.name)}"><img src="assets/item-placeholder.svg" data-ti-image="${esc(i.name)}" alt="${esc(i.name)}" loading="lazy" onerror="this.onerror=null;this.src='assets/item-placeholder.svg'"><strong>${esc(i.name)}</strong><p>${tiNum(i.quantity)}x</p><p>${tiNum(i.each)} por pessoa${i.remainder?` · sobra ${tiNum(i.remainder)}`:''}</p>${i.sellToNpc?`<p class="dica">NPC: ${esc(i.sellToNpc)}${i.priceAtNpc!=null?` · ${tiNum(i.priceAtNpc)} gold/un.`:''}</p>`:''}${i.imbuements.length?`<span class="ti-badge">Embuimento: ${i.imbuements.map(esc).join(', ')}</span>`:''}</article>`).join('')||'<p class="dica">Nenhum item nesta categoria.</p>'}</div></section>`).join('');
}
function tiRender(r){$('ti-result').innerHTML=tiHtml(r);}
async function tiProcess(){
  const id=++tiRequest;
  $('ti-process').disabled=true;
  try{const r=await window.pywebview.api.task_itens_analisar($('ti-input').value,$('ti-people').value);if(id!==tiRequest)return;tiResult=r;tiRender(r);if(!r.erro){const items=Object.values(r.groups).flat().map(i=>({name:i.name,id:i.id}));const images=await window.pywebview.api.task_itens_imagens(items);if(id===tiRequest)document.querySelectorAll('[data-ti-image]').forEach(img=>{if(images[img.dataset.tiImage])img.src=images[img.dataset.tiImage];});}}
  catch(e){if(id===tiRequest)$('ti-result').textContent='Não foi possível analisar os itens. Tente novamente.';}
  finally{if(id===tiRequest)$('ti-process').disabled=false;}
}
$('ti-process').addEventListener('click',tiProcess);
$('ti-input').addEventListener('paste',()=>{clearTimeout(tiPasteTimer);tiPasteTimer=setTimeout(()=>{if($('ti-input').value.trim())tiProcess();},100);});
$('ti-clear').addEventListener('click',()=>{clearTimeout(tiPasteTimer);++tiRequest;tiResult=null;$('ti-process').disabled=false;$('ti-input').value='';$('ti-result').textContent='';$('ti-input').focus();});
$('ti-people').addEventListener('change',()=>{if(tiResult)tiProcess();});
async function tiCopy(card){try{const ok=await window.pywebview.api.copiar(card.dataset.tiName);toast(ok?`${card.dataset.tiName} copiado!`:'Não consegui copiar.',!ok);}catch(e){toast('Não consegui copiar.',true);}}
function ligarLootHunt(){
  const container=$('h-res');
  container.querySelectorAll('[data-ti-name]').forEach(card=>{
    let down=null;
    card.addEventListener('pointerdown',e=>{down={x:e.clientX,y:e.clientY};});
    card.addEventListener('click',e=>{
      if(window.getSelection()?.toString()||e.detail>1)return;
      if(down&&Math.hypot(e.clientX-down.x,e.clientY-down.y)>5)return;
      tiCopy(card);
    });
    card.addEventListener('keydown',e=>{if(e.target===card&&(e.key==='Enter'||e.key===' ')){e.preventDefault();tiCopy(card);}});
  });
  const images=Array.from(container.querySelectorAll('[data-ti-image]'));
  if(!images.length)return;
  const items=Object.values(H.a.task_itens.groups).flat().map(i=>({name:i.name,id:i.id}));
  window.pywebview.api.task_itens_imagens(items).then(result=>{
    images.forEach(img=>{if(img.isConnected&&result[img.dataset.tiImage])img.src=result[img.dataset.tiImage];});
  }).catch(()=>{});
}
let tiDown=null;
$('ti-result').addEventListener('pointerdown',e=>{tiDown={x:e.clientX,y:e.clientY};});
$('ti-result').addEventListener('click',e=>{const card=e.target.closest('[data-ti-name]');if(!card||window.getSelection()?.toString()||e.detail>1)return;if(tiDown&&Math.hypot(e.clientX-tiDown.x,e.clientY-tiDown.y)>5)return;tiCopy(card);});
$('ti-result').addEventListener('keydown',e=>{const card=e.target.closest('[data-ti-name]');if(card&&e.target===card&&(e.key==='Enter'||e.key===' ')){e.preventDefault();tiCopy(card);}});
