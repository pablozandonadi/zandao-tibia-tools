(function () {
  'use strict';
  let busy = false, started = false, geracao = 0, canal = 'ia', perfil = '';
  const linhas = {ia: [], local: [], log: []};
  let registros = [], avisos = [];
  const el = id => document.getElementById(id);
  const bridge = () => window.pywebview && window.pywebview.api;
  function linha(classe, texto, entendi) {
    const row = document.createElement('div');
    row.className = classe;
    const fala = document.createElement('p');
    fala.textContent = texto;
    row.append(fala);
    if (entendi && entendi !== '—') {
      const nota = document.createElement('small');
      nota.textContent = `Entendi: ${entendi}`;
      row.append(nota);
    }
    return row;
  }
  function render(classe, texto, entendi, destino = canal) {
    const row = linha(classe, texto, entendi);
    linhas[destino].push({classe, texto, entendi});
    linhas[destino] = linhas[destino].slice(-100);
    if (destino === canal) { el('chat-mensagens').append(row); el('chat-mensagens').scrollTop = el('chat-mensagens').scrollHeight; }
    return row;
  }
  function selecionar(proximo) {
    if (!Object.hasOwn(linhas, proximo)) return;
    canal = proximo;
    for (const nome of ['local', 'log', 'ia']) {
      el('chat-canal-' + nome).setAttribute('aria-selected', String(nome === canal));
      el('chat-canal-' + nome).setAttribute('tabindex', nome === canal ? '0' : '-1');
      el('chat-canal-' + nome).setAttribute('aria-controls', 'chat-mensagens');
    }
    el('chat-mensagens').replaceChildren(...linhas[canal].map(m => linha(m.classe, m.texto, m.entendi)));
    el('chat-mensagens').scrollTop = el('chat-mensagens').scrollHeight;
    el('chat-form').hidden = canal === 'log';
    el('chat-canal-ajuda').textContent = canal === 'log' ? 'Registros e alertas do Tibia Tudo. Não lê o chat nem o log do jogo.' : canal === 'local' ? 'Comandos locais, sem envio à IA.' : 'Perguntas sobre Tibia e ferramentas do Tibia Tudo. Comandos locais primeiro.';
  }
  function atualizarLog() {
    // alertas já estão no histórico (alert.fired): não somar os avisos aqui
    const novo = registros.map(r => ({id:r.id, classe:'chat-registro', texto:r.texto})).slice(-50);
    if (JSON.stringify(novo) === JSON.stringify(linhas.log)) return;
    linhas.log = novo;
    if (canal === 'log') selecionar('log');
  }
  async function enviar(texto) {
    if (busy || canal === 'log') return;
    const atual = geracao, destino = canal;
    const botao = el('chat-form').querySelector('button[type=submit]');
    busy = true;
    botao.disabled = true;
    el('chat-limpar').disabled = true;
    render('chat-eu', texto, undefined, destino);
    el('chat-digitando').hidden = false;
    try {
      if (!bridge()) throw new Error('O aplicativo ainda está carregando. Tente de novo em instantes.');
      const dados = destino === 'local' ? await bridge().assistente_chat(texto, 'local') : await bridge().assistente_chat(texto);
      if (atual !== geracao) return;
      if (dados.erro) throw new Error(dados.erro);
      render('chat-bot', dados.resposta, dados.entendi, destino);
      if (window.assistenteLoad) window.assistenteLoad();
    } catch (error) { if (atual === geracao) render('chat-bot chat-erro', error.message || 'Não consegui responder agora.', undefined, destino); }
    finally { busy = false; botao.disabled = false; el('chat-limpar').disabled = false; el('chat-digitando').hidden = true; el('chat-texto').focus(); }
  }
  async function limpar(todos = false) {
    if (busy && !todos || canal === 'log' && !todos) return;
    const atual = ++geracao;
    if (todos) { linhas.ia = []; linhas.local = []; linhas.log = []; registros = []; avisos = []; }
    else linhas[canal] = [];
    selecionar(canal);
    el('chat-digitando').hidden = true;
    if (!todos && canal === 'local') return;
    try {
      if (!bridge()) throw new Error('O aplicativo ainda está carregando.');
      await bridge().assistente_chat_limpar();
    } catch (error) { if (atual === geracao) render('chat-bot chat-erro', error.message || 'Não consegui limpar a conversa.'); }
  }
  function trocarPerfil(proximo) { if (proximo !== perfil) { perfil = proximo; limpar(true); } }
  function boot() {
    if (started) return;
    started = true;
    el('chat-form').addEventListener('submit', event => {
      event.preventDefault();
      const texto = el('chat-texto').value.trim();
      if (!texto || busy || canal === 'log') return;
      el('chat-texto').value = '';
      enviar(texto);
    });
    el('chat-limpar').addEventListener('click', () => limpar());
    const canais = ['local', 'log', 'ia'];
    for (const nome of canais) {
      const tab = el('chat-canal-' + nome);
      tab.addEventListener('click', () => selecionar(nome));
      tab.addEventListener('keydown', event => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const index = event.key === 'Home' ? 0 : event.key === 'End' ? 2 : (canais.indexOf(nome) + (event.key === 'ArrowRight' ? 1 : 2)) % 3;
        selecionar(canais[index]);
        el('chat-canal-' + canais[index]).focus();
      });
    }
    if (typeof PERS_OUVINTES !== 'undefined') {
      const perfilAtual = () => {
        if (typeof MEUS === 'undefined') return '';
        const personagem = (MEUS.lista || []).find(p => p.nome === MEUS.atual);
        return JSON.stringify([MEUS.atual || '', personagem && personagem.mundo || '']);
      };
      perfil = perfilAtual();
      PERS_OUVINTES.push(() => trocarPerfil(perfilAtual()));
    }
    selecionar('ia');
  }
  window.chatEstado = data => {
    trocarPerfil(JSON.stringify([data.context.character_id || '', data.context.world_id || '']));
    registros = data.log || [];
    atualizarLog();
  };
  window.chatAvisos = data => { avisos = data || []; atualizarLog(); };
  if (typeof module !== 'undefined' && module.exports) module.exports = {render, enviar, limpar, boot, selecionar};
  boot();
})();
