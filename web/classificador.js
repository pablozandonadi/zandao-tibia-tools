// Classificador de dano dentro do app, com a sessão salva por hunt.
// A página é a da comunidade (lucasporfz/classificador): o app baixa os arquivos dela no PC, monta uma página só e roda numa caixa isolada
// (iframe sem acesso ao app). A "ponte" abaixo roda DENTRO dessa caixa: preenche os logs, clica em classificar e manda de volta os logs e o
// resultado, que ficam guardados na hunt (api.classificador_*). Depende de index.html: $, esc, toast, api, H.

// 1) roda antes dos scripts da página: a caixa isolada não tem localStorage, então damos um de memória para ela não quebrar
const CLS_SHIM = `(function () {
  try { window.localStorage.getItem('x'); } catch (e) {
    var mem = {};
    var arm = { getItem: function (k) { return Object.prototype.hasOwnProperty.call(mem, k) ? mem[k] : null; }, setItem: function (k, v) { mem[k] = String(v); },
      removeItem: function (k) { delete mem[k]; }, clear: function () { mem = {}; }, key: function (i) { return Object.keys(mem)[i] || null; } };
    try { Object.defineProperty(window, 'localStorage', { value: arm }); Object.defineProperty(window, 'sessionStorage', { value: arm }); } catch (e2) {}
  }
})();`;

// 2) roda depois da página carregar
const CLS_PONTE = `(function () {
  var $ = function (id) { return document.getElementById(id); };
  function avisar(m) { m.fonte = 'classificador'; parent.postMessage(m, '*'); }
  var ultimo = { local: null, server: null };
  setInterval(function () {            // o que foi colado ou aberto de arquivo vai para o app guardar
    var l = $('clsLocalInput'), s = $('clsServerInput');
    if (l && s && (l.value !== ultimo.local || s.value !== ultimo.server)) { ultimo = { local: l.value, server: s.value }; avisar({ tipo: 'logs', local: l.value, server: s.value }); }
  }, 1200);
  function foto() {                    // o resultado como HTML parado (os gráficos viram imagem)
    var r = $('clsResults'), c = r.cloneNode(true), o = r.querySelectorAll('canvas'), k = c.querySelectorAll('canvas');
    for (var i = 0; i < o.length; i++) {
      try { var im = document.createElement('img'); im.src = o[i].toDataURL('image/png'); im.style.maxWidth = '100%'; k[i].parentNode.replaceChild(im, k[i]); } catch (e) {}
    }
    var sc = c.querySelectorAll('script'); for (var j = 0; j < sc.length; j++) sc[j].remove();
    return c.innerHTML;
  }
  var espera = null, ultimaFoto = '';
  function agendar() {
    clearTimeout(espera);
    espera = setTimeout(function () {
      try {
        var r = $('clsResults');
        if (!r || r.style.display === 'none' || !r.children.length) return;
        var h = foto();
        if (h && h !== ultimaFoto) { ultimaFoto = h; avisar({ tipo: 'resultado', html: h }); }
      } catch (err) { avisar({ tipo: 'erro', msg: String(err && err.message || err) }); }
    }, 2500);
  }
  if ($('clsResults')) new MutationObserver(agendar).observe($('clsResults'), { childList: true, subtree: true, attributes: true, characterData: true });
  window.addEventListener('message', function (e) {
    var d = e.data;
    if (!d || d.fonte !== 'app' || d.tipo !== 'carregar') return;
    $('clsLocalInput').value = d.local || ''; $('clsServerInput').value = d.server || '';
    ultimo = { local: $('clsLocalInput').value, server: $('clsServerInput').value };   // já está guardado: não manda de volta
    ['clsLocalInput', 'clsServerInput'].forEach(function (id) { $(id).dispatchEvent(new Event('input', { bubbles: true })); });
    if (d.classificar) setTimeout(function () { $('btnClassify').click(); }, 300);
  });
  avisar({ tipo: 'pronto' });
})();`;

const CLS = { id: null, sessao: null, quadro: null, frame: null, modo: null, logs: null, html: null, pendente: false, paginaHtml: null };

const clsDataHora = (t) => (t ? new Date(t * 1000).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '');

async function clsAtualizarResumo() {
  const rot = $('cls-resumo');
  if (!rot) return;
  CLS.sessao = H.id ? await api.classificador_sessao(H.id) : null;
  const s = CLS.sessao;
  rot.textContent = s ? `sessão salva ${clsDataHora(s.t)} · ${s.linhas_local} linhas de local chat, ${s.linhas_server} de server log${s.tem_resultado ? ' · resultado salvo' : ''}`
    : CLS.pendente ? 'logs colados (serão guardados quando você salvar a hunt)' : 'nenhuma sessão salva nesta hunt';
  $('cls-ver').style.display = s && s.tem_resultado ? '' : 'none';
  $('cls-reclassificar').style.display = s ? '' : 'none';
  $('cls-apagar').style.display = s || CLS.pendente ? '' : 'none';
}

function clsLimparQuadro() {
  if (CLS.quadro) CLS.quadro.innerHTML = '';
  CLS.frame = null; CLS.modo = null;
}

// a hunt aberta mudou (abrir outra, nova hunt): zera a tela e mostra a sessão da hunt nova
async function clsMudouDeHunt() {
  CLS.logs = null; CLS.html = null; CLS.pendente = false;
  clsLimparQuadro();
  await clsAtualizarResumo();
  if ($('h-classificador') && $('h-classificador').open && CLS.sessao && CLS.sessao.tem_resultado) clsVerResultado();
}

// depois de salvar a hunt (agora ela tem id): guarda o que foi colado enquanto ela ainda não existia
async function clsAposSalvarHunt() {
  if (CLS.pendente && H.id && CLS.logs) {
    await api.classificador_salvar(H.id, CLS.logs.local, CLS.logs.server, CLS.html);
    CLS.pendente = false;
  }
  await clsAtualizarResumo();
}

let clsTimer = null;
function clsAgendarSalvar() {
  clearTimeout(clsTimer);
  clsTimer = setTimeout(async () => {
    if (!CLS.logs) return;
    if (!H.id) { CLS.pendente = true; await clsAtualizarResumo(); return; }
    const ok = await api.classificador_salvar(H.id, CLS.logs.local, CLS.logs.server, CLS.html);
    if (!ok && (CLS.logs.local || CLS.logs.server)) toast('Não consegui guardar a sessão do classificador.', true);
    await clsAtualizarResumo();
  }, 1500);
}

window.addEventListener('message', (e) => {
  const d = e.data;
  if (!CLS.frame || e.source !== CLS.frame.contentWindow || !d || d.fonte !== 'classificador') return;
  if (d.tipo === 'pronto') {
    const s = CLS.sessao;
    CLS.frame.contentWindow.postMessage({ fonte: 'app', tipo: 'carregar', local: s ? s.local : '', server: s ? s.server : '', classificar: CLS.modo === 'reclassificar' && !!s }, '*');
  } else if (d.tipo === 'logs') {
    CLS.logs = { local: d.local, server: d.server };
    CLS.html = null;             // logs novos: o resultado antigo não vale mais (o novo chega depois de classificar)
    clsAgendarSalvar();
  } else if (d.tipo === 'erro') {
    console.warn('classificador:', d.msg);
    CLS.erro = d.msg;
  } else if (d.tipo === 'resultado') {
    CLS.html = d.html;
    if (!CLS.logs && CLS.sessao) CLS.logs = { local: CLS.sessao.local, server: CLS.sessao.server };
    clsAgendarSalvar();
  }
});

async function clsMontarFrame(srcdoc, sandbox) {
  clsLimparQuadro();
  const f = document.createElement('iframe');
  f.className = 'class-frame';
  f.setAttribute('sandbox', sandbox);
  f.setAttribute('referrerpolicy', 'no-referrer');
  f.title = 'Classificador de dano';
  CLS.frame = f;
  f.srcdoc = srcdoc;
  CLS.quadro.appendChild(f);
}

async function clsAbrirAoVivo(modo) {
  CLS.modo = modo;
  CLS.quadro.innerHTML = '<div class="dica">Carregando o classificador (a primeira vez baixa os arquivos da página; precisa de internet)...</div>';
  if (!CLS.paginaHtml) {
    const r = await api.classificador_pagina();
    if (!r.ok) { CLS.quadro.innerHTML = `<div class="dica">${esc(r.erro || 'Não consegui carregar o classificador.')}</div>`; return; }
    CLS.paginaHtml = r.html.replace('<head>', `<head><script>${CLS_SHIM}<` + '/script>').replace('</body>', `<script>${CLS_PONTE}<` + '/script></body>');
  }
  await clsAtualizarResumo();
  clsMontarFrame(CLS.paginaHtml, 'allow-scripts allow-downloads');   // sem allow-same-origin: o código da página não alcança o app
}

async function clsVerResultado() {
  if (!H.id) return;
  const r = await api.classificador_resultado(H.id);
  if (!r.ok) { toast(r.erro || 'Essa hunt ainda não tem resultado salvo.', true); return; }
  clsMontarFrame(r.html, '');   // resultado parado, sem script nenhum
}

$('cls-ver').addEventListener('click', clsVerResultado);
$('cls-abrir').addEventListener('click', () => clsAbrirAoVivo('abrir'));
$('cls-reclassificar').addEventListener('click', () => clsAbrirAoVivo('reclassificar'));
$('cls-apagar').addEventListener('click', async () => {
  if (!confirm('Apagar os logs e o resultado guardados do classificador nesta hunt?')) return;
  if (H.id) await api.classificador_apagar(H.id);
  CLS.logs = null; CLS.html = null; CLS.pendente = false;
  clsLimparQuadro();
  await clsAtualizarResumo();
});
$('h-classificador').addEventListener('toggle', async () => {
  CLS.quadro = $('h-class-quadro');
  if (!$('h-classificador').open) return;
  await clsAtualizarResumo();
  if (!CLS.frame && CLS.sessao && CLS.sessao.tem_resultado) clsVerResultado();   // já tem resultado salvo: mostra na hora, sem reclassificar
});
CLS.quadro = $('h-class-quadro');
