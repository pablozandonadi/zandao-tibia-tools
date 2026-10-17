(function () {
  'use strict';
  let busy = false, started = false, geracao = 0, canal = 'ia', perfil = '';
  const linhas = {ia: [], local: [], log: [], help: []};
  const canais = ['local', 'log', 'help', 'ia'];
  let registros = [], avisos = [], mundo = [], mundoEm = 0, gMundo = 0;
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
  const AJUDA = {
    log: 'Registros e alertas do Tibia Tudo. Não lê o chat nem o log do jogo.',
    local: 'Comandos locais, sem envio à IA. No topo, as informações do mundo que também ficam na Home.',
    help: 'Instruções: o que digitar. Canal somente leitura.',
    ia: 'Perguntas sobre Tibia e ferramentas do Tibia Tudo. Comandos locais primeiro.'
  };
  const somenteLeitura = () => canal === 'log' || canal === 'help';
  function selecionar(proximo) {
    if (!Object.hasOwn(linhas, proximo)) return;
    canal = proximo;
    for (const nome of canais) {
      el('chat-canal-' + nome).setAttribute('aria-selected', String(nome === canal));
      el('chat-canal-' + nome).setAttribute('tabindex', nome === canal ? '0' : '-1');
      el('chat-canal-' + nome).setAttribute('aria-controls', nome === 'help' ? 'assistente-instrucoes' : 'chat-mensagens');
    }
    // Local Chat: as informações do mundo (as mesmas da Home) ficam no topo, antes da conversa
    el('chat-mensagens').replaceChildren(...(canal === 'local' ? mundo.map(texto => linha('chat-registro chat-mundo', texto)) : []), ...linhas[canal].map(m => linha(m.classe, m.texto, m.entendi)));
    el('chat-mensagens').scrollTop = el('chat-mensagens').scrollHeight;
    el('chat-mensagens').hidden = canal === 'help';
    el('assistente-instrucoes').hidden = canal !== 'help';
    el('chat-form').hidden = somenteLeitura();
    el('chat-canal-ajuda').textContent = AJUDA[canal];
    if (canal === 'local') mundoSeVelho();
  }
  function textoMundo(r) {
    const b = r.boostados || {}, dc = r.dream_court || {}, y = r.yasir || {}, s = r.servidor || {};
    const falta = Math.max(0, Math.floor((r.server_save_ms - Date.now()) / 60000));
    const hora = new Date(r.server_save_ms).toLocaleTimeString('pt-BR', {hour: '2-digit', minute: '2-digit'});
    return [
      `Rashid hoje: ${r.rashid || 'indisponível'}`,
      Number.isFinite(r.server_save_ms) ? `Server save em ${falta >= 60 ? `${Math.floor(falta / 60)}h${String(falta % 60).padStart(2, '0')}` : `${falta} min`} (às ${hora}, horário do seu PC)` : '',
      `Boss do dia: ${b.boss ? b.boss.nome : 'indisponível'}`,
      `Criatura do dia: ${b.criatura ? b.criatura.nome : 'indisponível'}`,
      dc.nome ? `Dream Court${r.mundo ? ' em ' + r.mundo : ''}: ${dc.nome}` : '',
      y.estado === 'presente' ? `Yasir: presente${y.cidade ? ' · ' + y.cidade : ''}` : y.estado === 'ausente' ? 'Yasir: ausente' : '',
      s.name && Number.isInteger(s.players_online) ? `${s.name}: ${s.players_online} jogadores online` : '',
      ...(r.avisos_mundo || []).slice(0, 3).map(x => `Aviso: ${x.texto}`)
    ].filter(Boolean);
  }
  // Mesma consulta da Home (zandaobot_buscar, com cache no app): no máximo uma por minuto, só com o Local Chat aberto
  async function carregarMundo() {
    if (!bridge() || !bridge().zandaobot_buscar) return;
    const atual = gMundo;
    mundoEm = Date.now();
    let novo = null;
    try { const r = await bridge().zandaobot_buscar(''); if (r && !r.erro) novo = textoMundo(r); } catch (error) { /* mantém o que já está na tela */ }
    if (atual !== gMundo || !novo && mundo.length) return;
    novo = novo || ['Informações do mundo indisponíveis agora.'];
    if (JSON.stringify(novo) === JSON.stringify(mundo)) return;
    mundo = novo;
    if (canal === 'local') selecionar('local');
  }
  function mundoSeVelho() { if (Date.now() - mundoEm > 60000) carregarMundo(); }
  function atualizarLog() {
    // alertas já estão no histórico (alert.fired): não somar os avisos aqui
    const novo = registros.map(r => ({id:r.id, classe:'chat-registro', texto:r.texto})).slice(-50);
    if (JSON.stringify(novo) === JSON.stringify(linhas.log)) return;
    linhas.log = novo;
    if (canal === 'log') selecionar('log');
  }
  async function enviar(texto) {
    if (busy || somenteLeitura()) return;
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
    if (busy && !todos || somenteLeitura() && !todos) return;
    const atual = ++geracao;
    if (todos) { linhas.ia = []; linhas.local = []; linhas.log = []; registros = []; avisos = []; mundo = []; mundoEm = 0; gMundo++; }
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
      if (!texto || busy || somenteLeitura()) return;
      el('chat-texto').value = '';
      enviar(texto);
    });
    el('chat-limpar').addEventListener('click', () => limpar());
    for (const nome of canais) {
      const tab = el('chat-canal-' + nome);
      tab.addEventListener('click', () => selecionar(nome));
      tab.addEventListener('keydown', event => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const index = event.key === 'Home' ? 0 : event.key === 'End' ? canais.length - 1 : (canais.indexOf(nome) + (event.key === 'ArrowRight' ? 1 : canais.length - 1)) % canais.length;
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
    if (canal === 'local') mundoSeVelho();
  };
  window.chatAvisos = data => { avisos = data || []; atualizarLog(); };
  if (typeof module !== 'undefined' && module.exports) module.exports = {render, enviar, limpar, boot, selecionar, carregarMundo};
  boot();
})();
