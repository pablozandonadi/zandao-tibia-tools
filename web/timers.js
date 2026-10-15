// Ajuda compacta: aparece ao passar o mouse ou focar o ícone.
function infoAudio(texto) {
  return `<span class="au-help" tabindex="0" aria-label="${esc(texto)}">i<span class="au-tooltip" role="tooltip">${esc(texto)}</span></span>`;
}
function compactarAjudaAudio(root) {
  root.querySelectorAll('.dica, .au-preview-note').forEach(note => {
    const texto = note.textContent.trim();
    if (!texto) return;
    const help = document.createElement('span');
    help.innerHTML = infoAudio(texto);
    const container = note.parentElement;
    const heading = container.querySelector(':scope > h3, :scope > h4, :scope > summary, :scope > .h-titulo h2, :scope > .linha-pasta');
    (heading || container).append(help.firstElementChild);
    note.remove();
  });
}

// Organiza os controles existentes sem substituir suas ações e estados.
function organizarFormAudio(t) {
  t.visual ||= {estilo: 'contorno', familia: 'Verdana', intensidade: 22};
  const card = document.querySelector('#au-form > .card');
  const children = [...card.children];
  const sec = (title, nodes, collapsible=false) => {
    const el = document.createElement(collapsible ? 'details' : 'section');
    el.className = 'au-section';
    if (collapsible) el.open = true;
    const heading = document.createElement(collapsible ? 'summary' : 'h3');
    heading.textContent = title; el.append(heading, ...nodes); return el;
  };
  card.append(sec('1. Ativação e contagem', children.slice(1,4)), sec('2. Som e aviso', [children[4]]));
  const visual = document.querySelector('#au-form-visual > .au-form');
  visual.querySelector(':scope > .dica')?.remove();
  visual.style.borderBottom = 'none';
  const groups = visual.querySelectorAll(':scope > .campos');
  const [alert, bar, color] = [...groups[0].children];
  const text = sec('Mensagem e estilo', [alert, groups[1]], true);
  text.id = 'au-aviso-editor';
  const effects = ['glow','sombra','borda'];
  const v = t.visual;
  const explicito = effects.some(k => Object.hasOwn(v,k));
  effects.forEach(k => {v[k] = explicito ? Boolean(v[k]) : v.estilo === ({glow:'glow',sombra:'sombra',borda:'contorno'}[k]);});
  text.insertAdjacentHTML('beforeend', `<div class="campos au-visual-options">
    <div><label class="campo-label" for="auf-familia">Fonte</label><select id="auf-familia">${['Segoe UI','Verdana','Tahoma','Arial'].map(n=>`<option>${n}</option>`).join('')}</select></div>
    <div><label class="campo-label" for="auf-intensidade">Raio do glow: <b id="auf-intensidade-v"></b></label><input type="range" id="auf-intensidade" min="1" max="30" value="${v.intensidade}"></div>
  </div><div class="au-effects">${effects.map(k=>`<div class="au-effect"><label class="check"><input type="checkbox" id="auf-${k}" ${v[k]?'checked':''}> ${ {glow:'Glow',sombra:'Sombra',borda:'Borda'}[k]}</label><input type="color" id="auf-cor-${k}" aria-label="Cor ${ {glow:'do glow',sombra:'da sombra',borda:'da borda'}[k]}" value="${v['cor_'+k] || (k==='glow'?corHex(t.cor_texto || t.cor):'#000000')}"></div>`).join('')}</div>`);
  groups[0].remove();
  visual.append(text);
  $('au-form-bar').replaceChildren(sec('Barra deste timer', [bar]));
  color.remove();
  $('au-form-cor').replaceChildren();
  t.cor_texto ||= t.cor || 'amarelo';
  t.cor_barra ||= t.cor || 'amarelo';
  t.barra_cor_tempo ??= Boolean(AU.cfg.barra.cor_tempo);
  const colorEditor = (target, kind, label) => {
    const field = kind==='texto' ? 'cor_texto' : 'cor_barra';
    const tempo = kind==='texto' ? 'texto_cor_tempo' : 'barra_cor_tempo';
    target.insertAdjacentHTML('beforeend', `<div class="au-color-settings"><label class="campo-label" for="auf-cor-${kind}">${label}</label><div class="linha-pasta"><input type="color" id="auf-cor-${kind}" value="${corHex(t[field])}">${CORES_AU.map(([k,n])=>`<button type="button" class="au-color-swatch" data-cor-${kind}="${k}" aria-label="${n}" title="${n}" style="background:${corHex(k)}"></button>`).join('')}</div><label class="check"><input type="checkbox" id="auf-${kind}-tempo" ${t[tempo]?'checked':''}> Cor pelo tempo ${infoAudio('A cor muda de verde para amarelo e vermelho conforme o tempo restante.')}</label></div>`);
    $('auf-cor-'+kind).addEventListener('input',()=>{t[field]=$('auf-cor-'+kind).value.toUpperCase();atualizarPreviaAudio();});
    target.querySelectorAll('[data-cor-'+kind+']').forEach(btn=>btn.addEventListener('click',()=>{t[field]=btn.getAttribute('data-cor-'+kind);$('auf-cor-'+kind).value=corHex(t[field]);atualizarPreviaAudio();}));
    $('auf-'+kind+'-tempo').addEventListener('change',()=>{t[tempo]=$('auf-'+kind+'-tempo').checked;atualizarPreviaAudio();});
  };
  colorEditor(text,'texto','Cor do texto');
  colorEditor($('au-form-bar'),'barra','Cor da barra');
  $('auf-familia').value=v.familia;
  function update() {
    effects.forEach(k=>{v[k]=$('auf-'+k).checked;v['cor_'+k]=$('auf-cor-'+k).value.toUpperCase();$('auf-cor-'+k).disabled=!v[k];});
    v.estilo='simples'; v.familia=$('auf-familia').value; v.intensidade=+$('auf-intensidade').value;
    $('auf-intensidade-v').textContent=v.intensidade;
    $('auf-intensidade').disabled=!v.glow;
    atualizarPreviaAudio();
  }
  ['auf-familia','auf-intensidade',...effects.flatMap(k=>['auf-'+k,'auf-cor-'+k])].forEach(id=>$(id).addEventListener('input',update));
  update();
  compactarAjudaAudio(card);
  compactarAjudaAudio($('au-visual'));
}

function corProgressoAudio(frac) {
  frac=Math.max(0,Math.min(1,frac));
  return '#'+[Math.round(255*Math.min(1,(1-frac)*2)),Math.round(230*Math.min(1,frac*2)),60].map(n=>n.toString(16).padStart(2,'0')).join('');
}
function sombraTextoAudio(v,cor) {
  const all=[];
  if(v.glow ?? v.estilo==='glow') all.push(`0 0 ${(v.intensidade || 22)/3}px ${v.cor_glow || cor}`,`0 0 ${v.intensidade || 22}px ${v.cor_glow || cor}`);
  if(v.sombra ?? v.estilo==='sombra') all.push(`3px 3px 3px ${v.cor_sombra || '#000000'}`);
  if(v.borda ?? v.estilo==='contorno') ['-1px -1px','1px -1px','-1px 1px','1px 1px'].forEach(pos=>all.push(`${pos} 0 ${v.cor_borda || '#000000'}`));
  return all.join(',') || 'none';
}
function atualizarPreviaAudio() {
  const el=$('au-text-preview');
  if (!el || typeof AU==='undefined' || !AU) return;
  const t=auEditando || {nome:'Timer',fonte:34,cor:'amarelo',alerta:true,barra:true};
  const v=t.visual || {estilo:'simples',familia:'Verdana',intensidade:22};
  const b=t.cfg_barra || AU.cfg.barra;
  const texto=t.texto_cor_tempo?corProgressoAudio(.65):corHex(t.cor_texto || t.cor);
  const barra=(t.barra_cor_tempo ?? b.cor_tempo)?corProgressoAudio(.65):corHex(t.cor_barra || t.cor);
  const msg=(t.mensagem || '').trim() || `${t.nome || 'Timer'} acabou!`;
  el.innerHTML=`<span class="au-preview-caption">Prévia do aviso de texto</span><div class="au-preview-text" style="color:${texto};font-family:'${v.familia}';font-size:${Math.min(28,t.fonte || 34)}px;text-shadow:${sombraTextoAudio(v,texto)};opacity:${t.alerta?1:.3}">${esc(msg)}</div>`;
  const tempo=b.tempo == null ? b.nome : b.tempo, vertical=b.orientacao==='vertical';
  const comprimento=vertical?Math.min(220,b.largura):b.largura;
  $('au-bar-preview').innerHTML=`<span class="au-preview-caption">Prévia da barra de contagem</span><div class="au-preview-bars ${vertical?'vertical':''}" style="opacity:${t.barra?1:.3}">
    ${b.nome ? `<div class="au-preview-bar-label" style="font-family:'${b.familia || 'Verdana'}'">${esc(t.nome || 'Timer')}</div>`:''}
    <div class="au-preview-track" style="height:${vertical?comprimento:b.espessura}px;width:${vertical?b.espessura:comprimento}px;border-radius:${['glow','arredondada'].includes(b.estilo)?6:0}px;border:${b.estilo==='classica'?'2px solid #000':b.estilo==='arredondada'?'1px solid #aab2bd':'none'}"><div class="au-preview-fill" style="height:${vertical?'65%':'100%'};width:${vertical?'100%':'65%'};${vertical?'position:absolute;bottom:0;':''}background:${barra};border-radius:inherit;box-shadow:${b.estilo==='glow'?`0 0 8px ${barra}`:'none'}"></div></div>
    ${tempo?`<div class="au-preview-bar-time" style="color:${barra};font-family:'${b.familia || 'Verdana'}';text-shadow:${sombraTextoAudio({estilo:b.texto_estilo, intensidade:6},barra)}">00:39</div>`:''}
  </div>`;
}

function atualizarEditorAudio() {
  const editando = Boolean(auEditando);
  document.querySelector('.au-editor-layout').hidden = !editando && !$('au-form').children.length;
  $('au-visual').hidden = !editando;
}

document.addEventListener('DOMContentLoaded', () => {
  const page = $('page-audio');
  compactarAjudaAudio(page);
  atualizarEditorAudio();
  const posicionarAjuda = event => {
    const help = event.target.closest('.au-help');
    if (!help) return;
    const tip = help.querySelector('.au-tooltip');
    const area = document.querySelector('.content').getBoundingClientRect();
    const rect = help.getBoundingClientRect();
    const width = Math.min(240, area.width - 24);
    tip.style.width = width + 'px';
    tip.style.maxWidth = 'none';
    tip.style.left = (Math.max(area.left + 12, Math.min(rect.left, area.right - width - 12)) - rect.left) + 'px';
    tip.style.right = 'auto';
    tip.style.top = rect.bottom + tip.offsetHeight + 8 > area.bottom ? (-tip.offsetHeight - 8) + 'px' : 'calc(100% + 8px)';
  };
  page.addEventListener('mouseover', posicionarAjuda);
  page.addEventListener('focusin', posicionarAjuda);
});

// Controles finos usam o mesmo evento do slider, inclusive na prévia ao vivo.
document.addEventListener('DOMContentLoaded', () => {
  ['aua-x', 'aua-y', 'aub-x', 'aub-y'].forEach(id => {
    const slider = $(id);
    const controls = document.createElement('div');
    controls.className = 'au-position-controls';
    controls.innerHTML = `<button type="button" class="btn btn-sm btn-primary" aria-label="Diminuir posição">−</button><input type="number" min="0" max="100" step="0.1" aria-label="${slider.labels[0].textContent.trim()} em porcentagem"><span>%</span><button type="button" class="btn btn-sm btn-primary" aria-label="Aumentar posição">+</button>`;
    slider.after(controls);
    const number = controls.querySelector('input');
    const update = value => {
      if (!Number.isFinite(value)) return;
      slider.value = Math.max(0, Math.min(100, Math.round(value * 10) / 10));
      slider.dispatchEvent(new Event('input', {bubbles: true}));
    };
    controls.querySelectorAll('button').forEach((button, index) => {
      button.addEventListener('click', () => update(+slider.value + (index ? .1 : -.1)));
    });
    number.addEventListener('change', () => { if (number.value !== '') update(number.valueAsNumber); });
    number.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); number.blur(); } });
    number.addEventListener('change', () => { number.value = slider.value; });
    const wheel = event => {
      if (event.ctrlKey) return;
      event.preventDefault();
      if (event.deltaY) update(+slider.value + (event.deltaY < 0 ? .1 : -.1));
    };
    controls.addEventListener('wheel', wheel, {passive: false});
    slider.addEventListener('wheel', wheel, {passive: false});
    // O formulário também pode carregar outro timer sem emitir input.
    new MutationObserver(() => { number.value = slider.value; }).observe($(id + '-v'), {childList: true});
    slider.addEventListener('input', () => { number.value = slider.value; });
    number.value = slider.value;
    controls.title = 'Ajuste fino: − / + ou roda do mouse em passos de 0,1%. Você também pode digitar a posição.';
  });
});
