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
  text.insertAdjacentHTML('beforeend', `<div class="campos au-visual-options">
    <div><label class="campo-label" for="auf-estilo">Formato da escrita</label><select id="auf-estilo">${[['glow','Brilho (glow)'],['contorno','Contorno preto'],['sombra','Sombra'],['simples','Simples']].map(([v,n])=>`<option value="${v}">${n}</option>`).join('')}</select></div>
    <div><label class="campo-label" for="auf-familia">Fonte</label><select id="auf-familia">${['Segoe UI','Verdana','Tahoma','Arial'].map(n=>`<option>${n}</option>`).join('')}</select></div>
    <div><label class="campo-label" for="auf-intensidade">Raio do brilho: <b id="auf-intensidade-v"></b></label><input type="range" id="auf-intensidade" min="1" max="30" value="${t.visual.intensidade}"></div>
  </div>`);
  groups[0].remove();
  visual.append(text);
  $('au-form-bar').replaceChildren(sec('Barra deste timer', [bar]));
  $('au-form-cor').replaceChildren(sec('Cor do timer', [color]));
  $('auf-estilo').value=t.visual.estilo; $('auf-familia').value=t.visual.familia;
  function update() {
    t.visual={estilo:$('auf-estilo').value,familia:$('auf-familia').value,intensidade:+$('auf-intensidade').value};
    $('auf-intensidade-v').textContent=t.visual.intensidade;
    $('auf-intensidade').disabled=t.visual.estilo!=='glow';
    atualizarPreviaAudio();
  }
  ['auf-estilo','auf-familia','auf-intensidade'].forEach(id=>$(id).addEventListener('input',update));
  update();
  compactarAjudaAudio(card);
  compactarAjudaAudio($('au-visual'));
}

function atualizarPreviaAudio() {
  const el=document.getElementById('au-text-preview');
  if (!el || typeof AU==='undefined' || !AU) return;
  const t=auEditando || {nome:'Poção', mensagem:'Poção acaba em 3s', fonte:34, cor:'amarelo', alerta:true, barra:true};
  const v=t.visual || {estilo:'contorno',familia:'Verdana',intensidade:22};
  const b=AU.cfg.barra, cor=corHex(t.cor);
  const shadow=(style,color,radius=22)=>({glow:`0 0 ${radius/3}px ${color},0 0 ${radius}px ${color}`,contorno:'-1px -1px 0 #000,1px -1px 0 #000,-1px 1px 0 #000,1px 1px 0 #000',sombra:'3px 3px 3px #000',simples:'none'}[style] || 'none');
  const msg=(t.mensagem || '').trim() || (t.antes ? `${t.nome || 'Timer'} acaba em ${Math.min(t.antes,t.duracao)}s` : `${t.nome || 'Timer'} acabou!`);
  el.innerHTML=`<span class="au-preview-caption">Prévia do aviso de texto</span>
    <div class="au-preview-text" style="color:${cor};font-family:'${v.familia}';font-size:${Math.min(28,t.fonte || 34)}px;text-shadow:${shadow(v.estilo,cor,v.intensidade)};opacity:${t.alerta?1:.3}">${esc(msg)}</div>`;
  const tempo=b.tempo == null ? b.nome : b.tempo;
  $('au-bar-preview').innerHTML=`<span class="au-preview-caption">Prévia da barra de contagem</span>
    <div style="opacity:${t.barra?1:.3};margin-top:30px">
      ${b.nome || tempo ? `<div class="au-preview-bar-label" style="width:${b.largura}px;font-family:'${b.familia || 'Verdana'}';text-shadow:${shadow(b.texto_estilo,cor,6)}"><span>${b.nome?esc(t.nome || 'Timer'):''}</span><span style="color:${cor}">${tempo?'00:39':''}</span></div>`:''}
      <div class="au-preview-track" style="height:${b.espessura}px;width:${b.largura}px;border-radius:${['glow','arredondada'].includes(b.estilo)?6:0}px;border:${b.estilo==='classica'?'2px solid #000':b.estilo==='arredondada'?'1px solid #aab2bd':'none'}">
        <div class="au-preview-fill" style="background:${b.cor_tempo?'#b3e63c':cor};border-radius:inherit;box-shadow:${b.estilo==='glow'?`0 0 8px ${cor}`:'none'}"></div>
      </div>
    </div>`;
}

function atualizarEditorAudio() {
  const editando = Boolean(auEditando);
  document.querySelector('.au-editor-layout').hidden = !editando;
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
