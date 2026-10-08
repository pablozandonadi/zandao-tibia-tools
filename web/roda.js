// ---------- roda (Wheel of Destiny): o planner oficial do tibia.com rodando numa caixa isolada ----------
// Cada PC baixa os arquivos do planner (roda.py) e eles rodam num iframe "sandbox" SEM acesso ao app (sem window.pywebview,
// sem os seus arquivos): o iframe só recebe os arquivos e o código, desenha a roda e mostra o resumo dos perks.
// Sem internet / se o planner mudar: a tela cai no plano B (título + código + link para o planner oficial).
// Usa do index.html: api (pywebview) e esc().
let RODA_ARQ = null;       // arquivos do planner (texto), baixados uma vez por sessão
const RODA_URL_OFICIAL = 'https://www.tibia.com/community/?subtopic=wheelofdestinyplanner&code=';
const linkRoda = (codigo) => RODA_URL_OFICIAL + encodeURIComponent(codigo);

const RODA_IFRAME_HTML = `<!doctype html><html><head><meta charset="utf-8"><style>
  html, body { margin: 0; background: #14171c; color: #e8e4d9; font: 13px/1.45 Arial, Helvetica, sans-serif; }
  body { padding: 6px 8px 10px; }
  .hide { display: none !important; }
  #wod-canvas { display: block; width: 522px; height: 522px; max-width: none; margin: 6px auto; }  /* sem esticar: o planner calcula o clique assumindo tamanho real */
  .cabecalho { display: flex; gap: 16px; flex-wrap: wrap; align-items: center; padding: 4px 0 6px; }
  input[type=text] { background: #1c2027; color: #e8e4d9; border: 1px solid #555; border-radius: 4px; padding: 2px 4px; width: 54px; }
  .oculto-leitura { display: none !important; }
  .editor-vocacao { display: flex; gap: 12px; flex-wrap: wrap; }
  .editor-vocacao label { text-transform: capitalize; cursor: pointer; }
  #botoes-pontos { display: flex; gap: 6px; margin: 4px 0; }
  #botoes-pontos button { background: #2a303b; color: #e8e4d9; border: 1px solid #555; border-radius: 4px; padding: 3px 10px; cursor: pointer; }
  #botoes-pontos button::before { content: attr(data-rot); }
  .painel { border: 1px solid #3a4150; border-radius: 8px; padding: 6px 10px; margin: 6px 0; background: #1a1e25; }
  .painel h4 { margin: 0 0 4px; font-size: 13px; color: #f5b301; }
  table { border-collapse: collapse; width: 100%; } td { padding: 1px 4px; vertical-align: top; } td:last-child { text-align: right; white-space: nowrap; }
  .nota { color: #9aa1b0; font-size: 11px; }
</style></head><body>
<p id="wod-warning" class="nota">Carregando a roda...</p>
<div id="wod-wrapper" class="hide">
  <div class="cabecalho">
    <span id="vocacoes" class="oculto-leitura editor-vocacao"></span>
    <span>Pontos de promoção: <span id="wod-reqpoints">0</span> / <input id="wod-limitpoints" type="text" maxlength="4" inputmode="numeric"></span>
  </div>
  <div class="oculto-leitura">
    <span id="wod-code-mobile"></span><span id="wod-code"></span>
    <button id="wod-code-copy"></button><button id="wod-code-url"></button><button id="wod-code-copy-mobile"></button><button id="wod-code-url-mobile"></button>
    <input id="wod-code-input" type="text"><button id="wod-code-import"></button><button id="wod-code-reset"></button><span id="wod-code-invalid"></span>
    <input id="wod-code-input-mobile" type="text"><button id="wod-code-import-mobile"></button><button id="wod-code-reset-mobile"></button><span id="wod-code-invalid-mobile"></span>
  </div>
  <canvas id="wod-canvas" width="522" height="522"></canvas>
  <div id="wod-selection-box" class="painel"></div>
  <div id="wod-information-box" class="painel"></div>
  <div id="botoes-pontos" class="oculto-leitura"><button id="wod-maxminus-button" data-rot="−−"></button><button id="wod-minus-button" data-rot="−"></button><button id="wod-plus-button" data-rot="+"></button><button id="wod-maxplus-button" data-rot="++"></button></div>
  <div class="painel"><h4 id="wod-dedication-perks-header"></h4><div id="wod-dedication-perks"></div></div>
  <div class="painel"><h4 id="wod-conviction-perks-header"></h4><div id="wod-conviction-perks"></div></div>
  <div class="painel"><h4 id="wod-revelation-perks-header"></h4><div id="wod-revelation-perks"></div></div>
  <div class="painel"><h4 id="wod-gem-perks-header"></h4><div id="wod-gem-perks"></div></div>
  <p id="wod-summary-note" class="nota"></p>
</div>
<script>
  // o que o planner espera encontrar na página do tibia.com
  var JS_DIR_IMAGES = 'https://static.tibia.com/images/';
  function CopyTextOfElement() {}
  function ActivateHelperDiv() {}
  function DeactivateHelperDiv() {}
  // 1 -> I, 4 -> IV, 12 -> XII (o planner usa para escrever os níveis dos perks)
  function toRomanNumeral(n) {
    if (isNaN(n) || n < 0 || parseInt(n) !== n) return n;
    var d = String(+n).split(''), k = ['', 'C', 'CC', 'CCC', 'CD', 'D', 'DC', 'DCC', 'DCCC', 'CM', '', 'X', 'XX', 'XXX', 'XL', 'L', 'LX', 'LXX', 'LXXX', 'XC',
      '', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX'], r = '', i = 3;
    while (i--) r = (k[+d.pop() + (i * 10)] || '') + r;
    return Array(+d.join('') + 1).join('M') + r;
  }
  history.replaceState = function () {};
  function alturaConteudo() { return Math.ceil(document.body.getBoundingClientRect().height) + 16; }
  function avisar(o) { parent.postMessage(Object.assign({ fonte: 'roda' }, o), '*'); }
  window.onerror = function (m) { avisar({ tipo: 'erro', msg: String(m) }); };
  function injetar(texto) { var s = document.createElement('script'); s.text = texto; document.head.appendChild(s); }
  window.addEventListener('message', function (e) {
    var d = e.data;
    if (!d || d.tipo !== 'iniciar') return;
    try {
      var vocs = '';
      ['knight', 'druid', 'sorcerer', 'paladin', 'monk'].forEach(function (v) {
        vocs += '<label for="wod-vocation_' + v + '"><input id="wod-vocation_' + v + '" type="radio" name="wod-vocation" value="' + v + '">' + v + '</label>';
      });
      document.getElementById('vocacoes').innerHTML = vocs;
      if (d.editavel) {   // modo "montar a roda": libera a vocação e os botões de pontos (a seleção/preenchimento é no desenho)
        document.getElementById('vocacoes').classList.remove('oculto-leitura');
        document.getElementById('botoes-pontos').classList.remove('oculto-leitura');
      }
      injetar(d.jquery); injetar(d.skillgrid); injetar(d.planner);
      var textos = 'data:application/json;charset=utf-8;base64,' + btoa(unescape(encodeURIComponent(d.strings)));
      runWodPlanner(textos, { warning: 'wod-warning', wrapper: 'wod-wrapper', vocationRadio: 'wod-vocation', reqPoints: 'wod-reqpoints', limitPoints: 'wod-limitpoints',
        code: 'wod-code', codeCopy: 'wod-code-copy', codeUrl: 'wod-code-url', codeImport: 'wod-code-import', codeReset: 'wod-code-reset', codeInput: 'wod-code-input',
        codeInvalid: 'wod-code-invalid', codeMobile: 'wod-code-mobile', codeCopyMobile: 'wod-code-copy-mobile', codeUrlMobile: 'wod-code-url-mobile',
        codeImportMobile: 'wod-code-import-mobile', codeResetMobile: 'wod-code-reset-mobile', codeInputMobile: 'wod-code-input-mobile', codeInvalidMobile: 'wod-code-invalid-mobile',
        selectionBox: 'wod-selection-box', maxMinus: 'wod-maxminus-button', minus: 'wod-minus-button', maxPlus: 'wod-maxplus-button', plus: 'wod-plus-button',
        infoBox: 'wod-information-box', canvas: 'wod-canvas', dedicationPerks: 'wod-dedication-perks', convictionPerks: 'wod-conviction-perks',
        revelationPerks: 'wod-revelation-perks', gemPerks: 'wod-gem-perks', summaryNote: 'wod-summary-note' });
      var tentativas = 0, espera = setInterval(function () {
        tentativas++;
        var pronto = !document.getElementById('wod-wrapper').classList.contains('hide');
        if (pronto) {
          clearInterval(espera);
          document.getElementById('wod-code-input').value = d.codigo;
          document.getElementById('wod-code-import').click();
          var ultimo = '';   // avisa o app do código atual sempre que ele muda (montar/editar a roda)
          setInterval(function () {
            var c = (document.getElementById('wod-code').textContent || document.getElementById('wod-code-mobile').textContent || '').trim();
            if (c && c !== ultimo) { ultimo = c; avisar({ tipo: 'codigo', codigo: c }); }
          }, 400);
          setTimeout(function () { avisar({ tipo: 'pronto', codigo: (document.getElementById('wod-code').textContent || '').trim(), altura: alturaConteudo() }); }, 400);
        } else if (tentativas > 80) {
          clearInterval(espera);
          avisar({ tipo: 'erro', msg: 'O planner não terminou de carregar.' });
        }
      }, 150);
    } catch (err) { avisar({ tipo: 'erro', msg: String(err && err.message || err) }); }
  });
  if (window.ResizeObserver) new ResizeObserver(function () { avisar({ tipo: 'altura', altura: alturaConteudo() }); }).observe(document.body);
  avisar({ tipo: 'carregado' });
</script></body></html>`;

// cria o visualizador dentro de `alvo` (um elemento). Resolve true quando a roda aparece, false se caiu no plano B.
async function mostrarRoda(alvo, codigo, { editavel = false, aoMudar = null } = {}) {
  alvo.innerHTML = '<div class="dica">Carregando a roda...</div>';
  if (!RODA_ARQ) {
    const r = await api.roda_arquivos();
    if (!r.ok) { alvo.innerHTML = planoBRoda(codigo, r.erro); return false; }
    RODA_ARQ = r.arquivos;
  }
  return new Promise((resolve) => {
    const frame = document.createElement('iframe');
    frame.className = 'roda-frame';
    frame.setAttribute('sandbox', 'allow-scripts');   // sem allow-same-origin: o código de fora não alcança o app
    frame.srcdoc = RODA_IFRAME_HTML;
    let terminou = false;
    const fim = (ok, msg) => {
      if (terminou) return;
      terminou = true;
      clearTimeout(limite);
      if (!ok) { frame.remove(); window.removeEventListener('message', ouvir); alvo.innerHTML = planoBRoda(codigo, msg); }
      resolve(ok);
    };
    const ouvir = (e) => {
      if (!frame.isConnected) { window.removeEventListener('message', ouvir); return; }   // a roda foi trocada ou fechada
      if (e.source !== frame.contentWindow || !e.data || e.data.fonte !== 'roda') return;
      const d = e.data;
      if (d.tipo === 'carregado') {
        frame.contentWindow.postMessage({ tipo: 'iniciar', codigo, editavel, jquery: RODA_ARQ['jquery.js'], skillgrid: RODA_ARQ['skillgrid.js'],
          planner: RODA_ARQ['planner.js'], strings: RODA_ARQ['strings.json'] }, '*');
      } else if (d.tipo === 'pronto') { frame.style.height = (d.altura + 8) + 'px'; fim(true); }
      else if (d.tipo === 'altura') frame.style.height = (d.altura + 8) + 'px';
      else if (d.tipo === 'codigo') { if (aoMudar) aoMudar(d.codigo); }
      else if (d.tipo === 'erro') { console.warn('roda:', d.msg); fim(false, 'O planner da Tibia não abriu aqui (' + d.msg + ').'); }
    };
    window.addEventListener('message', ouvir);
    const limite = setTimeout(() => fim(false, 'O planner demorou demais para abrir.'), 20000);
    alvo.innerHTML = '';
    alvo.appendChild(frame);
  });
}

// plano B: sem visualização, mas com o código e o link do planner oficial
function planoBRoda(codigo, motivo) {
  return `<div class="dica">${esc(motivo || 'Não consegui mostrar a roda.')}</div>
    <div class="roda-planob"><code>${esc(codigo)}</code>
      <a class="btn btn-sm" href="${esc(linkRoda(codigo))}" target="_blank" rel="noopener noreferrer">Abrir no planner do tibia.com</a></div>`;
}

// ---------- cadastro das rodas (Configurações) ----------
let RODAS = [];   // rodas cadastradas: [{id, titulo, codigo, vocacao}]
async function carregarRodas() { RODAS = (await api.roda_listar()) || []; return RODAS; }
// roda da última hunt desse personagem (valor inicial de uma hunt nova); {} = sem roda
const rodaInicial = async (personagem) => (await api.hunt_ultima_roda(personagem || '')) || {};
const codigoCurto = (c) => (c.length > 16 ? c.slice(0, 16) + '…' : c);

function desenharRodasConfig() {
  $('rodas-lista').innerHTML = RODAS.length ? RODAS.map((r) => `<div class="roda-item">
      <div class="roda-nome"><b>${esc(r.titulo)}</b> <span class="chip chip-neutro">${esc(r.vocacao)}</span> <code class="dim" title="${esc(r.codigo)}">${esc(codigoCurto(r.codigo))}</code></div>
      <div class="acoes"><button class="btn btn-sm" data-roda-ver="${esc(r.id)}">👁 Ver</button><button class="btn btn-sm" data-roda-editar="${esc(r.id)}" title="Abrir a roda para editar">🛠 Editar</button><button class="btn btn-sm" data-roda-renomear="${esc(r.id)}" title="Renomear">✎</button>
        <button class="btn btn-sm btn-danger" data-roda-apagar="${esc(r.id)}" title="Apagar">✕</button></div></div>`).join('')
    : '<div class="dica">Nenhuma roda cadastrada ainda.</div>';
}
async function montarRodasConfig() { await carregarRodas(); desenharRodasConfig(); }

async function adicionarRoda() {
  const r = await api.roda_adicionar($('roda-titulo').value, $('roda-codigo').value);
  if (!r.ok) { $('roda-msg').textContent = r.erro; return; }
  $('roda-titulo').value = ''; $('roda-codigo').value = '';
  $('roda-msg').textContent = `✔ "${r.roda.titulo}" adicionada (${r.roda.vocacao}).`;
  await montarRodasConfig();
}
$('roda-add').addEventListener('click', adicionarRoda);
$('roda-codigo').addEventListener('keydown', (e) => { if (e.key === 'Enter') adicionarRoda(); });
$('cfg-rodas').addEventListener('click', async (e) => {
  const b = e.target.closest('[data-roda-ver],[data-roda-editar],[data-roda-renomear],[data-roda-apagar]');
  if (!b) return;
  const d = b.dataset, roda = RODAS.find((r) => r.id === (d.rodaVer || d.rodaEditar || d.rodaRenomear || d.rodaApagar));
  if (!roda) return;
  if (d.rodaVer) {
    rodaEdicao = null;
    $('roda-editor-barra').style.display = 'none';
    $('roda-view-titulo').textContent = `${roda.titulo} (${roda.vocacao})`;
    $('roda-view-box').style.display = '';
    await mostrarRoda($('roda-view'), roda.codigo);
    $('roda-view-box').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } else if (d.rodaEditar) {
    abrirEditorRoda(roda);
  } else if (d.rodaRenomear) {
    const novo = prompt('Novo nome da roda:', roda.titulo);
    if (novo === null) return;
    await api.roda_renomear(roda.id, novo);
    await montarRodasConfig();
  } else if (d.rodaApagar) {
    if (!confirm(`Apagar a roda "${roda.titulo}"? As hunts que já usaram essa roda continuam com o nome e o código dela.`)) return;
    await api.roda_remover(roda.id);
    await montarRodasConfig();
  }
});
$('roda-view-fechar').addEventListener('click', () => { rodaEdicao = null; $('roda-view').innerHTML = ''; $('roda-view-box').style.display = 'none'; });

// ---------- montar / editar uma roda: o planner com os controles liberados; o app acompanha o código que ele gera ----------
let rodaEdicao = null;   // {id: da roda sendo editada (ou null = roda nova), codigo: o código atual no planner}
const RODA_VAZIA = 'K0Y2AgDP4jAQA';   // roda vazia de Knight; a vocação se troca nos botões do próprio planner
async function abrirEditorRoda(roda) {
  rodaEdicao = { id: roda ? roda.id : null, codigo: roda ? roda.codigo : RODA_VAZIA };
  $('roda-view-titulo').textContent = roda ? `Editando: ${roda.titulo}` : 'Montar uma roda nova';
  $('roda-ed-nome').value = roda ? roda.titulo : '';
  $('roda-ed-atualizar').style.display = roda ? '' : 'none';
  $('roda-ed-salvar').textContent = roda ? 'Salvar como nova' : 'Salvar roda';
  $('roda-ed-status').textContent = 'Monte a roda abaixo (clique na fatia e use os botões, ou botão direito para preencher). O código é acompanhado sozinho.';
  $('roda-editor-barra').style.display = '';
  $('roda-view-box').style.display = '';
  $('roda-view-box').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  await mostrarRoda($('roda-view'), rodaEdicao.codigo, { editavel: true, aoMudar: (c) => {
    if (!rodaEdicao) return;
    rodaEdicao.codigo = c;
    $('roda-ed-status').textContent = `Código atual: ${codigoCurto(c)}`;
  } });
}
$('roda-montar').addEventListener('click', () => abrirEditorRoda(null));
$('roda-ed-salvar').addEventListener('click', async () => {
  if (!rodaEdicao) return;
  const r = await api.roda_adicionar($('roda-ed-nome').value, rodaEdicao.codigo);
  if (!r.ok) { $('roda-ed-status').textContent = r.erro; return; }
  $('roda-msg').textContent = `✔ "${r.roda.titulo}" salva (${r.roda.vocacao}).`;
  $('roda-ed-status').textContent = `✔ Salva como "${r.roda.titulo}".`;
  await montarRodasConfig();
});
$('roda-ed-atualizar').addEventListener('click', async () => {
  if (!rodaEdicao || !rodaEdicao.id) return;
  const r = await api.roda_atualizar(rodaEdicao.id, rodaEdicao.codigo, $('roda-ed-nome').value);
  if (!r.ok) { $('roda-ed-status').textContent = r.erro; return; }
  $('roda-msg').textContent = `✔ "${r.roda.titulo}" atualizada.`;
  $('roda-ed-status').textContent = `✔ Alterações salvas em "${r.roda.titulo}".`;
  await montarRodasConfig();
});

// ---------- a roda dentro da hunt (seção "Seu personagem nesta hunt") ----------
// H.entrada.roda: {titulo, codigo} = escolhida; {} = sem roda; null = hunt antiga com roda não informada (não é enviada ao salvar)
function resumoRoda() {
  const r = H.entrada.roda;
  return r == null ? 'roda não informada' : !r.codigo ? 'sem roda' : `Roda: ${r.titulo}`;
}
function htmlRodaHunt() {
  const r = H.entrada.roda;
  const sel = r && r.codigo ? RODAS.find((x) => x.codigo === r.codigo) : null;
  const opcoes = RODAS.map((x) => `<option value="${esc(x.id)}" ${sel && sel.id === x.id ? 'selected' : ''}>${esc(x.titulo)} (${esc(x.vocacao)})</option>`).join('');
  const guardada = r && r.codigo && !sel ? `<option value="__hunt" selected>${esc(r.titulo)} (guardada nesta hunt)</option>` : '';
  return `<h3 class="sub3" style="margin-top:18px">Roda (Wheel of Destiny)</h3>
    <div class="dica perso-desc">Escolha a roda que você usou nesta hunt. Cadastre as suas em Configurações.</div>
    ${r == null ? '<div class="dica" style="margin:0 0 8px">Roda não informada nesta hunt: escolha para marcar, ou <button class="btn btn-sm" data-marcar-vazio="roda">Marcar sem roda</button></div>' : ''}
    <div class="roda-linha"><select id="h-roda-sel">${r == null ? '<option value="" selected disabled>Escolher a roda...</option>' : ''}
      <option value="__nenhuma" ${r && !r.codigo ? 'selected' : ''}>Sem roda</option>${opcoes}${guardada}</select>
      ${r && r.codigo ? '<button class="btn btn-sm" data-roda-hunt-ver>👁 Ver a roda</button>' : ''}
      ${RODAS.length ? '' : '<span class="dica">Nenhuma roda cadastrada: cadastre em Configurações.</span>'}</div>
    <div id="h-roda-view" style="margin-top:10px"></div>`;
}
$('h-res').addEventListener('change', (e) => {
  if (e.target.id !== 'h-roda-sel') return;
  const v = e.target.value;
  if (v === '__hunt') return;                       // a roda guardada na hunt já é a escolhida
  if (v === '__nenhuma') H.entrada.roda = {};
  else { const x = RODAS.find((r) => r.id === v); if (x) H.entrada.roda = { titulo: x.titulo, codigo: x.codigo }; }
  redesenharPerso();
});
$('h-res').addEventListener('click', (e) => {
  if (!e.target.closest('[data-roda-hunt-ver]') || !H.entrada.roda || !H.entrada.roda.codigo) return;
  mostrarRoda($('h-roda-view'), H.entrada.roda.codigo);
});
