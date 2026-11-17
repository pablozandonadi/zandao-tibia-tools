// ---------- roda (Wheel of Destiny): o planner oficial do tibia.com rodando numa caixa isolada ----------
// Cada PC baixa os arquivos do planner (roda.py) e eles rodam num iframe "sandbox" SEM acesso ao app (sem window.pywebview,
// sem os seus arquivos): o iframe só recebe os arquivos e o código, desenha a roda e mostra o resumo dos perks.
// Sem internet / se o planner mudar: a tela cai no plano B (título + código + link para o planner oficial).
// Usa do index.html: api (pywebview) e esc().
let RODA_ARQ = null;       // arquivos do planner (texto), baixados uma vez por sessão
const RODA_URL_OFICIAL = 'https://www.tibia.com/community/?subtopic=wheelofdestinyplanner&code=';
// roda nova (update de inverno 2026: vessels e gemas): código "W26.…", aberto no planner da comunidade (prévia não oficial; ver roda.py)
const RODA_SITE_NOVA = 'https://tibia-destiny-winter-workbench.palescone.chatgpt.site/';
const ehRodaNova = (codigo) => /^W26\./.test(codigo || '');
let RODA_NOVA_HTML = null; // a página do planner novo, baixada uma vez por sessão
const linkRoda = (codigo) => (ehRodaNova(codigo) ? RODA_SITE_NOVA + '#build=' + codigo : RODA_URL_OFICIAL + encodeURIComponent(codigo));

// Ponte que vai no fim da página do planner novo (roda depois dos scripts dele, dentro da caixa isolada): carrega o código,
// avisa o app do código atual e do resumo (para o Combat Stats) e repassa o que a caixa não consegue fazer sozinha (copiar, avisos).
const ponteRodaNova = (codigo, editavel) => `<style>
  header { display: none !important; }
  dialog[open] { position: fixed; top: 12px; margin: 0 auto; }
  body.leitura .vocRow, body.leitura .sector-selection .actions, body.leitura #gemActions,
  body.leitura .codes-panel .code-row:nth-of-type(2) { display: none !important; }
</style><script>(function () {
  var CODIGO = ${JSON.stringify(codigo || '').replace(/</g, '\\u003c')}, EDITAVEL = ${editavel ? 'true' : 'false'}, SITE = document.baseURI;
  function avisar(o) { parent.postMessage(Object.assign({ fonte: 'roda' }, o), '*'); }
  var $q = function (s) { return document.querySelector(s); };
  if (!$q('[data-code-export]') || typeof BASE === 'undefined') { avisar({ tipo: 'erro', msg: 'o planner da roda nova não carregou' }); return; }
  window.onerror = function (m) { avisar({ tipo: 'erro', msg: String(m) }); };
  if (!EDITAVEL) document.body.classList.add('leitura');
  // a caixa isolada não tem área de transferência: quem copia é o app ("Copy Full URL" sai como about:srcdoc, vira o link do site)
  try { Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: function (t) {
    avisar({ tipo: 'copiar', texto: String(t).replace(/^about:srcdoc/, SITE) }); return Promise.resolve(); } } }); } catch (e) {}
  // os avisos (toast) e as janelas do planner ficam no topo da caixa, que é alta: o app mostra o aviso e rola até a janela
  new MutationObserver(function () { var t = ($q('#toast').textContent || '').trim(); if (t && EDITAVEL && !/preset loaded/i.test(t)) avisar({ tipo: 'aviso', texto: t }); })
    .observe($q('#toast'), { childList: true, characterData: true, subtree: true });
  new MutationObserver(function () { if ($q('#dialog').open) avisar({ tipo: 'rolar' }); }).observe($q('#dialog'), { attributes: true });
  if (CODIGO) { $q('[data-code-import]').value = CODIGO; $q('[data-load-code]').click(); }
  var VALOR = /^([+-]?[0-9][0-9,]*([.][0-9]+)?%?|Locked|Stage [0-9]|[IVX]+)$/, ROM = ['', 'I', 'II', 'III', 'IV', 'V'];
  // "Perks Summary" no formato do resumo do planner oficial (nome, valor, nome, valor...), que o Combat Stats já entende
  function lerResumo() {
    var voc = ($q('[name=vocation]:checked') || {}).value, conv = (BASE.convictions || {})[voc] || [];
    return [].map.call(document.querySelectorAll('.summaryGrid > section'), function (sec) {
      var linhas = [];
      sec.querySelectorAll('tr').forEach(function (tr) {
        var td = tr.querySelectorAll('td'); if (td.length < 2) return;
        var nome = td[0].textContent.trim(), val = td[1].textContent.trim(), m;
        if (nome === 'Unlocked') { nome = 'Vessels unlocked'; val = val.split('/')[0].trim(); }
        else if ((m = /^Stage (I{1,3})$/.exec(val))) val = 'Stage ' + m[1].length;
        else if ((m = /^([0-9]+) filled$/.exec(val))) {   // conviction: N fatias cheias com o mesmo perk
          var p = conv.find(function (x) { return x.name === nome; }), n = +m[1], d = p && /^([+-][0-9.]+)(%?)/.exec(p.description || '');
          val = /^Augmented /.test(nome) ? ROM[Math.min(n, 5)] : d ? (d[1][0] === '-' ? '-' : '+') + (+(Math.abs(parseFloat(d[1])) * n).toFixed(2)) + d[2] : '';
        } else if (nome === 'Hit Points / Mana / Capacity') { var v = val.replace(/ each$/, ''); linhas.push('Hit Points', v, 'Mana', v, 'Capacity', v); return; }
        if (!nome || !val || nome === 'Promotion Points') return;
        if (VALOR.test(val)) linhas.push(nome, val); else if (val !== '—' && !/pending/i.test(val)) linhas.push(nome + ': ' + val);
      });
      return { titulo: ((sec.querySelector('h3') || {}).textContent || '').trim(), linhas: linhas };
    });
  }
  // o body do site ocupa a janela inteira (cresceria junto com a caixa): mede pelo fim do <main>; 0 = caixa escondida (outra aba)
  var MAIN = $q('main') || document.body, ultimo = '', ultimaAltura = 0;
  function altura() { var b = MAIN.getBoundingClientRect().bottom; return b > 0 ? Math.ceil(b + window.scrollY) + 24 : 0; }
  setInterval(function () {
    var h = altura(), c = ($q('[data-code-export]') || {}).value || '';
    if (h && h !== ultimaAltura) { ultimaAltura = h; avisar({ tipo: 'altura', altura: h }); }
    if (/^W26[.]/.test(c) && c !== ultimo) { ultimo = c; avisar({ tipo: 'codigo', codigo: c }); setTimeout(function () { avisar({ tipo: 'resumo', codigo: c, secoes: lerResumo() }); }, 300); }
  }, 400);
  setTimeout(function () { ultimaAltura = altura(); avisar({ tipo: 'pronto', altura: ultimaAltura || undefined }); }, 300);
})();</script>`;

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
  body.leitura #vocacoes, body.leitura #painel-selecao { display: none !important; }   /* só ver: sem editar a roda */
  .PerkWrapper { margin: 0 0 8px; } .Bold { font-weight: bold; margin-bottom: 2px; }
  .SkillValue, .LargePerkValue, .ModEffectValue, .VesselValue { color: #cfcabd; }
  .LargePerkName { font-weight: bold; color: #f5b301; }
  .SkillPercentage { position: relative; height: 18px; background: #2a303b; border: 1px solid #555; border-radius: 4px; overflow: hidden; margin-bottom: 8px; }
  .PercentageBar { position: absolute; left: 0; top: 0; bottom: 0; width: 0; background: #a8741a; }
  .SkillPercentage .Text { position: relative; text-align: center; line-height: 18px; font-size: 12px; }
  .SmallButtonRow { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; }
  .SmallButtonRow input[type=button] { background: #2a303b; color: #e8e4d9; border: 1px solid #666; border-radius: 4px; padding: 4px 10px; cursor: pointer; }
  .SmallButtonRow input[type=button]:hover { border-color: #f5b301; }
  .GemWrapper, .VesselWrapper { margin-bottom: 8px; }
  .GemModsWrapper { display: grid; gap: 4px; }
  .GemDropdownWrapper select { width: 100%; }
  .ModEffectWrapper { display: flex; gap: 6px; align-items: center; min-height: 18px; margin-bottom: 4px; }
  .ModGrades img { height: 12px; margin-right: 2px; }
  /* ícones recortados de uma folha: o planner define o tamanho e desloca a imagem; o recorte (overflow) vem do CSS do site */
  #wod-selection-box [id$="-icon"], #wod-information-box [id$="-icon"] { overflow: hidden; flex: none; }
  #wod-selection-box [id$="-icon"] img, #wod-information-box [id$="-icon"] img { max-width: none; display: block; }
  .painel { border: 1px solid #3a4150; border-radius: 8px; padding: 6px 10px; margin: 6px 0; background: #1a1e25; }
  .painel h4 { margin: 0 0 4px; font-size: 13px; color: #f5b301; }
  table { border-collapse: collapse; width: 100%; } td { padding: 1px 4px; vertical-align: top; } td:last-child { text-align: right; white-space: nowrap; }
  .nota { color: #9aa1b0; font-size: 11px; }
  .popup-dica { position: fixed; z-index: 9999; max-width: 300px; background: #0b0d12; border: 2px solid #e7b73c; border-radius: 8px; padding: 8px 10px;
    font-size: 12px; line-height: 1.4; color: #e8eaf0; box-shadow: 0 4px 14px rgba(0,0,0,.65); pointer-events: none; }
  .popup-dica b { color: #e7b73c; display: block; margin-bottom: 3px; }
  /* duas colunas: o desenho (522 px, tamanho real) à esquerda; seleção/gemas, informação e resumos à direita */
  #wod-wrapper { display: grid; grid-template-columns: 540px minmax(300px, 1fr); gap: 14px; align-items: start; }
  .col-info { min-width: 0; }
  .resumos { display: grid; grid-template-columns: repeat(auto-fit, minmax(270px, 1fr)); gap: 8px; }
  .resumos .painel, .col-info .painel { margin: 0 0 8px; }
  .painel:empty { display: none; }
  select { background: #1c2027; color: #e8e4d9; border: 1px solid #555; border-radius: 4px; padding: 3px 4px; max-width: 100%; }
  select:disabled { opacity: .45; }
  @media (max-width: 920px) { #wod-wrapper { display: block; } .resumos { grid-template-columns: 1fr; } }
</style></head><body>
<p id="wod-warning" class="nota">Carregando a roda...</p>
<div id="wod-wrapper" class="hide">
  <div class="col-roda">
    <div class="cabecalho">
      <span id="vocacoes" class="editor-vocacao"></span>
      <span>Pontos de promoção: <span id="wod-reqpoints">0</span> / <input id="wod-limitpoints" type="text" maxlength="4" inputmode="numeric"></span>
    </div>
    <canvas id="wod-canvas" width="522" height="522"></canvas>
  </div>
  <div class="col-info">
    <div class="painel" id="painel-selecao"><h4>Seleção</h4><div id="wod-selection-box"></div></div>
    <div class="painel" id="painel-info"><h4>Informação</h4><div id="wod-information-box"></div></div>
    <div class="resumos">
      <div class="painel"><h4 id="wod-dedication-perks-header"></h4><div id="wod-dedication-perks"></div></div>
      <div class="painel"><h4 id="wod-conviction-perks-header"></h4><div id="wod-conviction-perks"></div></div>
      <div class="painel"><h4 id="wod-revelation-perks-header"></h4><div id="wod-revelation-perks"></div></div>
      <div class="painel"><h4 id="wod-gem-perks-header"></h4><div id="wod-gem-perks"></div></div>
    </div>
    <p id="wod-summary-note" class="nota"></p>
  </div>
  <div class="oculto-leitura">
    <span id="wod-code-mobile"></span><span id="wod-code"></span>
    <button id="wod-code-copy"></button><button id="wod-code-url"></button><button id="wod-code-copy-mobile"></button><button id="wod-code-url-mobile"></button>
    <input id="wod-code-input" type="text"><button id="wod-code-import"></button><button id="wod-code-reset"></button><span id="wod-code-invalid"></span>
    <input id="wod-code-input-mobile" type="text"><button id="wod-code-import-mobile"></button><button id="wod-code-reset-mobile"></button><span id="wod-code-invalid-mobile"></span>
  </div>
</div>
<script>
  // o que o planner espera encontrar na página do tibia.com
  var JS_DIR_IMAGES = 'https://static.tibia.com/images/';
  function CopyTextOfElement() {}
  // popup simples dos "?" (no tibia.com é o HelperDiv): título e texto aparecem ao passar o mouse e somem ao sair
  var popupDica = null;
  function DeactivateHelperDiv() { if (popupDica) { popupDica.remove(); popupDica = null; } }
  function ActivateHelperDiv(el, titulo, texto) {
    DeactivateHelperDiv();
    if (!titulo && !texto) return;
    popupDica = document.createElement('div');
    popupDica.className = 'popup-dica';
    popupDica.innerHTML = (titulo ? '<b>' + titulo + '</b>' : '') + (texto ? '<div>' + texto + '</div>' : '');
    document.body.appendChild(popupDica);
    var alvo = el && el[0] ? el[0] : el;   // o planner passa um objeto jQuery
    var r = alvo.getBoundingClientRect(), w = popupDica.offsetWidth, h = popupDica.offsetHeight, vw = document.documentElement.clientWidth;
    popupDica.style.left = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), Math.max(8, vw - w - 8)) + 'px';
    popupDica.style.top = ((r.bottom + 6 + h > window.innerHeight && r.top - h - 6 > 0) ? r.top - h - 6 : r.bottom + 6) + 'px';
  }
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
  // Seleção e Informação: o planner espera esta estrutura pronta (ids com o nome da caixa) e só mostra/esconde e preenche.
  function montarPainel(p, comSelecao) {
    var perk = function (k, t) { return '<div id="' + p + '-' + k + '-wrapper" class="PerkWrapper"><div id="' + p + '-' + k + '-header" class="Bold">' + t + '</div><div id="' + p + '-' + k + '-value" class="SkillValue"></div></div>'; };
    var mod = function (n) {
      return '<div class="GemDropdownWrapper">' + (comSelecao ? '<select name="' + p + '-gem-mod' + n + '-dropdown" class="GemDropdown"></select>' : '') + '</div>'
        + '<div class="ModEffectWrapper"><div class="ModEffectIconWrapper"><div id="' + p + '-gem-mod' + n + '-icon"></div></div><div id="' + p + '-gem-mod' + n + '" class="ModEffectValue"></div></div>';
    };
    var grau = function (n) { return '<img id="' + p + '-gem-modgrades-' + n + '" class="hide" src="https://static.tibia.com/images/community/wheelofdestiny/icon_modgrade4.png">'; };
    var botoes = '<div id="' + p + '-buttons" class="SmallButtonRow"><input type="button" id="wod-maxminus-button" value="− Max"><input type="button" id="wod-minus-button" value="− 1">'
      + '<input type="button" id="wod-plus-button" value="+ 1"><input type="button" id="wod-maxplus-button" value="+ Max"></div>';
    return '<div id="' + p + '-bar" class="SkillPercentage hide"><span id="' + p + '-bar-filling" class="PercentageBar"></span><div id="' + p + '-bar-text" class="Text">0/100</div></div>'
      + '<div id="' + p + '-empty" class="nota">' + (comSelecao ? 'Selecione uma fatia ou um encaixe de gema.' : 'Passe o mouse sobre uma fatia.') + '</div>'
      + '<div id="' + p + '-medium" class="hide">' + perk('dedication', 'Dedication Perk') + perk('conviction', 'Conviction Perk')
        + (comSelecao ? botoes : '<div id="' + p + '-fillinfo" class="nota"></div>') + '</div>'
      + '<div id="' + p + '-large" class="hide"><div id="' + p + '-revelation-wrapper" class="PerkWrapper"><div id="' + p + '-revelation-header" class="Bold">Revelation Perk</div>'
        + '<div id="' + p + '-revelation-icon"></div><div id="' + p + '-revelation-name" class="LargePerkName"></div><div id="' + p + '-revelation-description" class="LargePerkValue"></div></div></div>'
      + '<div id="' + p + '-socket" class="hide"><div id="' + p + '-gem-wrapper" class="GemWrapper"><div id="' + p + '-gem-modgrades" class="ModGrades">' + grau(1) + grau(2) + grau(3) + '</div>'
        + '<div id="' + p + '-gem-name" class="Bold">Gem</div><div id="' + p + '-gem-mod-wrapper" class="GemModsWrapper">' + mod(1) + mod(2) + mod(3) + '</div></div>'
        + '<div id="' + p + '-vessel-wrapper" class="VesselWrapper"><div id="' + p + '-vessel-header" class="Bold">Vessel</div><div id="' + p + '-vessel-value" class="VesselValue"></div></div></div>';
  }
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
      document.getElementById('wod-selection-box').innerHTML = montarPainel('wod-selection-box', true);
      document.getElementById('wod-information-box').innerHTML = montarPainel('wod-information-box', false);
      if (!d.editavel) document.body.classList.add('leitura');   // só ver: esconde a vocação e a Seleção (botões, gemas)
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
          // lê os 4 painéis de resumo do planner (Dedication, Conviction, Revelation e Gems) para o Combat Stats
          var lerResumo = function () {
            return ['dedication', 'conviction', 'revelation', 'gem'].map(function (k) {
              var t = document.getElementById('wod-' + k + '-perks-header'), c = document.getElementById('wod-' + k + '-perks');
              var linhas = [];   // um item por elemento-folha (nome e valor vêm em elementos separados)
              if (c) {
                var folhas = c.querySelectorAll('*');
                for (var i = 0; i < folhas.length; i++) {
                  if (folhas[i].children.length === 0) { var tx = (folhas[i].textContent || '').trim(); if (tx) linhas.push(tx); }
                }
                if (!folhas.length && (c.textContent || '').trim()) linhas.push(c.textContent.trim());
              }
              return { titulo: (t ? t.innerText : k).trim(), linhas: linhas };
            });
          };
          var ultimo = '';   // avisa o app do código atual sempre que ele muda (montar/editar a roda)
          setInterval(function () {
            var c = (document.getElementById('wod-code').textContent || document.getElementById('wod-code-mobile').textContent || '').trim();
            if (c && c !== ultimo) { ultimo = c; avisar({ tipo: 'codigo', codigo: c }); setTimeout(function () { avisar({ tipo: 'resumo', codigo: c, secoes: lerResumo() }); }, 900); }
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
// nova = planner da roda nova (padrão para códigos "W26."; um código antigo aberto nele é convertido pelo próprio planner)
async function mostrarRoda(alvo, codigo, { editavel = false, aoMudar = null, aoResumo = null, nova = ehRodaNova(codigo) } = {}) {
  // por padrão guarda o resumo do planner e mostra embaixo da roda as revelações, augments e gemas com as bolinhas
  if (!aoResumo) aoResumo = (c, s) => { guardarResumoRoda(c, s); mostrarPontosRoda(alvo, s); };
  alvo.innerHTML = '<div class="dica">Carregando a roda...</div>';
  let pagina = RODA_IFRAME_HTML;
  if (nova) {
    if (!RODA_NOVA_HTML) {
      const r = await api.roda_pagina_inverno();
      if (!r.ok) { alvo.innerHTML = planoBRoda(codigo, r.erro); return false; }
      RODA_NOVA_HTML = r.html;
    }
    const ponte = ponteRodaNova(codigo, editavel);
    pagina = RODA_NOVA_HTML.includes('</body>') ? RODA_NOVA_HTML.replace('</body>', () => ponte + '</body>') : RODA_NOVA_HTML + ponte;
  } else if (!RODA_ARQ) {
    const r = await api.roda_arquivos();
    if (!r.ok) { alvo.innerHTML = planoBRoda(codigo, r.erro); return false; }
    RODA_ARQ = r.arquivos;
  }
  return new Promise((resolve) => {
    const frame = document.createElement('iframe');
    frame.className = 'roda-frame';
    frame.setAttribute('sandbox', 'allow-scripts');   // sem allow-same-origin: o código de fora não alcança o app
    frame.srcdoc = pagina;
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
      } else if (d.tipo === 'pronto') { if (d.altura) frame.style.height = (d.altura + 8) + 'px'; fim(true); }
      else if (d.tipo === 'altura') frame.style.height = (d.altura + 8) + 'px';
      else if (d.tipo === 'codigo') { if (aoMudar) aoMudar(d.codigo); }
      else if (d.tipo === 'resumo') { if (aoResumo) aoResumo(d.codigo, d.secoes); }
      else if (d.tipo === 'copiar') copiarDaRoda(String(d.texto || ''));
      else if (d.tipo === 'aviso') toast(String(d.texto || '').slice(0, 300));
      else if (d.tipo === 'rolar') frame.scrollIntoView({ behavior: 'smooth', block: 'start' });
      else if (d.tipo === 'erro') { console.warn('roda:', d.msg); fim(false, 'O planner da Tibia não abriu aqui (' + d.msg + ').'); }
    };
    window.addEventListener('message', ouvir);
    const limite = setTimeout(() => fim(false, 'O planner demorou demais para abrir.'), 20000);
    alvo.innerHTML = '';
    alvo.appendChild(frame);
  });
}

// o foco fica dentro da caixa da roda, então o navigator.clipboard do app recusa: copia pelo Windows (api.copiar)
async function copiarDaRoda(texto) {
  if (await api.copiar(texto)) toast(/^https?:/.test(texto) ? 'Link da roda copiado.' : 'Código da roda copiado.');
  else toast('Não consegui copiar sozinho: clique no código do quadro Code e use Ctrl+A e Ctrl+C.', true);
}

// o resumo que o planner calcula (perks de cada seção) fica guardado por código, para o Combat Stats e o comparativo
const RODA_RESUMO = {};
function guardarResumoRoda(codigo, secoes) {
  if (!codigo || !Array.isArray(secoes)) return;
  RODA_RESUMO[codigo] = secoes;
  api.roda_guardar_resumo(codigo, secoes);
}

// bolinhas das revelações (●), augments e gemas (◆) embaixo da roda: o que o planner já liberou com os pontos escolhidos
const bolinhas = (p) => (p.tipo === 'revelacao' ? '●' : '◆').repeat(p.n) + (p.tipo === 'revelacao' ? '○' : '◇').repeat(Math.max(0, p.de - p.n));
function htmlPontosRoda(pontos) {
  if (!pontos || !pontos.length) return '';
  const grupo = (titulo, tipos) => {
    const l = pontos.filter((p) => tipos.includes(p.tipo));
    return l.length ? `<div class="pt-grupo"><h5>${titulo}</h5>${l.map((p) => `<div class="pt-lin ${p.n ? '' : 'zero'}"><span>${esc(p.rotulo)}</span><b class="pt-bol ${p.tipo}" title="${esc(p.texto)}">${bolinhas(p)}</b></div>`).join('')}</div>` : '';
  };
  return `<div class="pt-box"><h4>Revelações e gemas</h4><div class="pt-grade">${grupo('Revelações (estágios)', ['revelacao'])}${grupo('Augments', ['aumento'])}${grupo('Gemas (ressonância)', ['gema'])}</div>
    <p class="dica" style="margin:6px 0 0">● estágio liberado de uma revelação · ◆ nível de um augment ou da ressonância das gemas · ○ ◇ ainda não liberado</p></div>`;
}
async function mostrarPontosRoda(alvo, secoes) {
  if (!alvo || !alvo.isConnected) return;
  const pontos = await api.roda_pontos(secoes);
  let caixa = alvo.querySelector('.roda-pontos');
  if (!caixa) { caixa = document.createElement('div'); caixa.className = 'roda-pontos'; alvo.appendChild(caixa); }
  caixa.innerHTML = htmlPontosRoda(pontos);
}

// plano B: sem visualização, mas com o código e o link do planner oficial
function planoBRoda(codigo, motivo) {
  return `<div class="dica">${esc(motivo || 'Não consegui mostrar a roda.')}</div>
    <div class="roda-planob"><code>${esc(codigo)}</code>
      <a class="btn btn-sm" href="${esc(linkRoda(codigo))}" target="_blank" rel="noopener noreferrer">Abrir no ${ehRodaNova(codigo) ? 'site do planner novo' : 'planner do tibia.com'}</a></div>`;
}

// ---------- cadastro das rodas (Configurações) ----------
let RODAS = [];   // rodas cadastradas: [{id, titulo, codigo, vocacao}]
async function carregarRodas() { RODAS = (await api.roda_listar()) || []; return RODAS; }
// roda da última hunt desse personagem (valor inicial de uma hunt nova); {} = sem roda
const rodaInicial = async (personagem) => (await api.hunt_ultima_roda(personagem || '')) || {};
const codigoCurto = (c) => (c.length > 16 ? c.slice(0, 16) + '…' : c);

const linhaRodaCfg = (r) => `<div class="roda-nome"><b>${esc(r.titulo)}</b> <span class="chip chip-neutro">${esc(r.vocacao)}</span>${ehRodaNova(r.codigo) ? ' <span class="chip chip-neutro" title="Roda do update de inverno (vessels e gemas)">❄ nova</span>' : ''} <code class="dim" title="${esc(r.codigo)}">${esc(codigoCurto(r.codigo))}</code></div>
      <div class="acoes"><button class="btn btn-sm" data-roda-ver="${esc(r.id)}">👁 Ver</button><button class="btn btn-sm" data-roda-editar="${esc(r.id)}" title="Abrir a roda para editar">🛠 Editar</button>${ehRodaNova(r.codigo) ? '' : `<button class="btn btn-sm" data-roda-converter="${esc(r.id)}" title="Abre esta roda no planner novo (update de inverno, com vessels e gemas) para salvar no formato novo">❄ Converter</button>`}<button class="btn btn-sm" data-roda-renomear="${esc(r.id)}" title="Renomear">✎</button>
        <button class="btn btn-sm btn-danger" data-roda-apagar="${esc(r.id)}" title="Apagar">✕</button></div>`;
function desenharRodasConfig() {
  const minhas = doPers(RODAS, MEUS.atual);
  $('rodas-lista').innerHTML = htmlDonoDaLista(RODAS, MEUS.atual, 'as rodas')
    + (minhas.length ? minhas.map((r) => `<div class="roda-item">${linhaRodaCfg(r)}</div>`).join('') : '<div class="dica">Nenhuma roda cadastrada para este personagem ainda.</div>')
    + htmlAntigos(semDono(RODAS), 'roda', (r) => `<div class="roda-nome"><b>${esc(r.titulo)}</b> <span class="chip chip-neutro">${esc(r.vocacao)}</span></div>`, 'as rodas');
}
async function montarRodasConfig() { await carregarRodas(); desenharRodasConfig(); }

async function adicionarRoda() {
  const r = await api.roda_adicionar($('roda-titulo').value, $('roda-codigo').value, MEUS.atual || '');
  if (!r.ok) { $('roda-msg').textContent = r.erro; return; }
  $('roda-titulo').value = ''; $('roda-codigo').value = '';
  $('roda-msg').textContent = `✔ "${r.roda.titulo}" adicionada (${r.roda.vocacao}).`;
  await montarRodasConfig();
}
$('roda-add').addEventListener('click', adicionarRoda);
$('roda-codigo').addEventListener('keydown', (e) => { if (e.key === 'Enter') adicionarRoda(); });
$('cfg-rodas').addEventListener('click', async (e) => {
  const b = e.target.closest('[data-roda-ver],[data-roda-editar],[data-roda-converter],[data-roda-renomear],[data-roda-apagar]');
  if (!b) return;
  const d = b.dataset, roda = RODAS.find((r) => r.id === (d.rodaVer || d.rodaEditar || d.rodaConverter || d.rodaRenomear || d.rodaApagar));
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
  } else if (d.rodaConverter) {
    abrirEditorRoda(roda, { nova: true });
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
// roda nova (sem roda, código "W26." ou "Converter") abre no planner novo; o código antigo continua no planner do tibia.com
async function abrirEditorRoda(roda, { nova = !roda || ehRodaNova(roda.codigo) } = {}) {
  rodaEdicao = { id: roda ? roda.id : null, codigo: roda ? roda.codigo : '' };
  $('roda-view-titulo').textContent = !roda ? 'Montar uma roda nova' : nova && !ehRodaNova(roda.codigo) ? `Convertendo para a roda nova: ${roda.titulo}` : `Editando: ${roda.titulo}`;
  $('roda-ed-nome').value = roda ? roda.titulo : '';
  $('roda-ed-atualizar').style.display = roda ? '' : 'none';
  $('roda-ed-salvar').textContent = roda ? 'Salvar como nova' : 'Salvar roda';
  $('roda-ed-status').textContent = nova
    ? 'Monte a roda abaixo: clique na fatia e use os botões (dois cliques enche, botão direito enche/esvazia); gemas em "Configure Vessels". O código é acompanhado sozinho.'
    : 'Monte a roda abaixo (clique na fatia e use os botões, ou botão direito para preencher). O código é acompanhado sozinho.';
  $('roda-editor-barra').style.display = '';
  $('roda-view-box').style.display = '';
  $('roda-view-box').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  await mostrarRoda($('roda-view'), rodaEdicao.codigo, { editavel: true, nova, aoMudar: (c) => {
    if (!rodaEdicao) return;
    rodaEdicao.codigo = c;
    $('roda-ed-status').textContent = `Código atual: ${codigoCurto(c)}`;
  } });
}
$('roda-montar').addEventListener('click', () => abrirEditorRoda(null));
$('roda-ed-salvar').addEventListener('click', async () => {
  if (!rodaEdicao) return;
  if (!rodaEdicao.codigo) { $('roda-ed-status').textContent = 'Espere a roda carregar.'; return; }
  const r = await api.roda_adicionar($('roda-ed-nome').value, rodaEdicao.codigo, MEUS.atual || '');
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

// ---------- menu Wheel of Destiny: o planner novo inteiro, com "Salvar nas minhas rodas" ----------
// a caixa isolada não guarda nada; o último código fica no localStorage do app para a roda voltar como estava
let WOD_CODIGO = '';
async function abrirWod() {
  if ($('wod-view').querySelector('iframe')) return;   // já aberto: mantém o que está sendo montado
  let ultimo = '';
  try { ultimo = localStorage.getItem('zt-wod-ultimo') || ''; } catch (e) { /* sem localStorage: começa vazia */ }
  await mostrarRoda($('wod-view'), ultimo, { editavel: true, nova: true, aoMudar: (c) => {
    WOD_CODIGO = c;
    try { localStorage.setItem('zt-wod-ultimo', c); } catch (e) { /* só conveniência */ }
  } });
}
$('wod-salvar').addEventListener('click', async () => {
  if (!WOD_CODIGO) { $('wod-status').textContent = 'Espere a roda carregar.'; return; }
  const r = await api.roda_adicionar($('wod-nome').value, WOD_CODIGO, MEUS.atual || '');
  if (!r.ok) { $('wod-status').textContent = r.erro; return; }
  $('wod-status').textContent = `✔ Salva como "${r.roda.titulo}" (${r.roda.vocacao})${MEUS.atual ? ' nas rodas de ' + MEUS.atual : ''}.`;
  await carregarRodas();
});

// ---------- a roda dentro da hunt (seção "Seu personagem nesta hunt") ----------
// H.entrada.roda: {titulo, codigo} = escolhida; {} = sem roda; null = hunt antiga com roda não informada (não é enviada ao salvar)
function resumoRoda() {
  const r = H.entrada.roda;
  return r == null ? 'roda não informada' : !r.codigo ? 'sem roda' : `Roda: ${r.titulo}`;
}
function htmlRodaHunt() {
  const r = H.entrada.roda;
  const dono = H.entrada.personagem || MEUS.atual, minhas = doPers(RODAS, dono);
  const sel = r && r.codigo ? minhas.find((x) => x.codigo === r.codigo) : null;
  const opcoes = minhas.map((x) => `<option value="${esc(x.id)}" ${sel && sel.id === x.id ? 'selected' : ''}>${esc(x.titulo)} (${esc(x.vocacao)})</option>`).join('');
  const guardada = r && r.codigo && !sel ? `<option value="__hunt" selected>${esc(r.titulo)} (guardada nesta hunt)</option>` : '';
  return `<h3 class="sub3" style="margin-top:18px">Roda (Wheel of Destiny)</h3>
    <div class="dica perso-desc">Escolha a roda que você usou nesta hunt. Cadastre as suas em Configurações.</div>
    ${r == null ? '<div class="dica" style="margin:0 0 8px">Roda não informada nesta hunt: escolha para marcar, ou <button class="btn btn-sm" data-marcar-vazio="roda">Marcar sem roda</button></div>' : ''}
    <div class="roda-linha"><select id="h-roda-sel">${r == null ? '<option value="" selected disabled>Escolher a roda...</option>' : ''}
      <option value="__nenhuma" ${r && !r.codigo ? 'selected' : ''}>Sem roda</option>${opcoes}${guardada}</select>
      ${r && r.codigo ? '<button class="btn btn-sm" data-roda-hunt-ver>👁 Ver a roda</button>' : ''}
      ${minhas.length ? '' : `<span class="dica">Nenhuma roda de ${esc(dono || 'personagem')}: cadastre em Configurações${semDono(RODAS).length ? ' ou vincule as antigas a ele' : ''}.</span>`}</div>
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
