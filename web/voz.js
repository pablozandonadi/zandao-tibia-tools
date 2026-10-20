(function () {
  'use strict';
  let snapshot = {timers: []}, received = 0, started = false, busy = false;
  const cards = new Map(), vistos = new Set();
  let primeiro = true, ciclo = 0;
  const el = id => document.getElementById(id);
  const bridge = () => window.pywebview && window.pywebview.api;
  function format(seconds) {
    seconds = Math.max(0, Math.ceil(seconds));
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
  }
  function countdown() {
    const elapsed = (performance.now() - received) / 1000;
    for (const timer of snapshot.timers || []) {
      const card = cards.get(timer.id);
      if (card) card.querySelector('time').textContent = format(timer.restante - elapsed);
    }
  }
  function render(data) {
    snapshot = data;
    received = performance.now();
    el('voz-status').textContent = data.detalhe || 'Preparando assistente…';
    el('voz-status').dataset.estado = data.estado || '';
    el('voz-esfera').dataset.estado = data.estado || 'espera';
    el('voz-esfera').setAttribute('aria-label', data.direto ? 'Desligar comandos diretos' : 'Ligar comandos diretos');
    el('voz-esfera').setAttribute('aria-pressed', String(Boolean(data.direto)));
    el('voz-esfera').disabled = busy || !data.microfone || data.estado === 'preparando';
    el('voz-ouvi').textContent = data.ouvi || 'Aguardando “Hey Tibia”.';
    el('voz-entendi').textContent = data.entendi || '—';
    el('voz-resposta').textContent = data.resposta || 'As respostas aparecerão aqui.';
    el('voz-microfone').textContent = data.microfone ? 'Pausar microfone' : (data.estado === 'erro' ? 'Tentar novamente' : 'Retomar microfone');
    el('voz-microfone').disabled = busy;
    if (window.chatAvisos) window.chatAvisos(data.avisos || []);
    el('voz-avisos').textContent = (data.avisos || []).map(aviso => aviso.texto).join(' · ');
    el('voz-online-enabled').checked = data.online_enabled === true;
    el('voz-online-status').textContent = data.online_enabled ? 'IA do chat ativada.' : (data.online_configured ? 'Acesso salvo; IA do chat desligada.' : 'Chat só com comandos locais. Nenhum acesso online salvo.');
    const ids = new Set((data.timers || []).map(timer => timer.id));
    for (const [id, card] of cards) {
      if (!ids.has(id)) { card.remove(); cards.delete(id); }
    }
    for (const timer of el('voz-lista') ? (data.timers || []) : []) {
      let card = cards.get(timer.id);
      if (!card) {
        card = document.createElement('article');
        card.className = 'voz-timer card calmo';
        const label = document.createElement('strong');
        const remaining = document.createElement('time');
        remaining.setAttribute('aria-label', 'Tempo restante');
        const cancel = document.createElement('button');
        cancel.className = 'btn btn-sm';
        cancel.textContent = 'Cancelar';
        cancel.setAttribute('aria-label', `Cancelar timer de ${timer.label}`);
        cancel.addEventListener('click', () => mutate('voz_cancelar', timer.id));
        card.append(label, remaining, cancel);
        el('voz-lista').append(card);
        cards.set(timer.id, card);
      }
      card.querySelector('strong').textContent = `Timer de ${timer.label}`;
      card.querySelector('button').disabled = busy;
    }
    if (el('voz-vazio')) el('voz-vazio').hidden = ids.size > 0;
    if (el('voz-quantidade')) el('voz-quantidade').textContent = `${ids.size} ${ids.size === 1 ? 'timer ativo' : 'timers ativos'}`;
    countdown();
  }
  // Avisos (timer, boss, stamina, mercado) valem em qualquer aba: toast + som, uma vez por id; no 1º estado só marca como vistos.
  function bipe() {
    const Contexto = window.AudioContext || window.webkitAudioContext;
    const ctx = new Contexto(), osc = ctx.createOscillator();
    osc.frequency.value = 880;
    osc.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.2);
  }
  async function tocar() {
    try { await bridge().audio_tocar('padrao:Potion.mp3', 100); } catch (error) { try { bipe(); } catch (e) { /* sem áudio: segue só com o toast */ } }
  }
  function notificar(avisos) {
    const novos = avisos.filter(aviso => !vistos.has(aviso.id));
    novos.forEach(aviso => vistos.add(aviso.id));
    if (primeiro) { primeiro = false; return; }
    if (!novos.length) return;
    for (const aviso of novos) { try { window.toast(aviso.texto); } catch (error) { /* toast ausente */ } }
    tocar();
  }
  async function refresh() {
    if (!bridge() || busy) return;
    busy = true;
    try {
      const data = await bridge().voz_estado();
      if (data.erro) throw new Error(data.erro);
      render(data);
      notificar(data.avisos || []);
    } catch (error) { el('voz-feedback').textContent = error.message || 'Não consegui consultar os timers.'; }
    finally {
      busy = false;
      el('voz-microfone').disabled = false;
      el('voz-esfera').disabled = !snapshot.microfone || snapshot.estado === 'preparando';
      for (const card of cards.values()) card.querySelector('button').disabled = false;
    }
  }
  async function mutate(method, ...args) {
    if (!bridge() || busy) return;
    busy = true;
    el('voz-feedback').textContent = '';
    if (el('voz-criar')) el('voz-criar').disabled = true;
    try {
      const data = await bridge()[method](...args);
      if (data.erro) throw new Error(data.erro);
      render(data);
    } catch (error) { el('voz-feedback').textContent = error.message || 'Não consegui concluir o comando.'; }
    finally {
      busy = false;
      if (el('voz-criar')) el('voz-criar').disabled = false;
      el('voz-microfone').disabled = false;
      el('voz-esfera').disabled = !snapshot.microfone || snapshot.estado === 'preparando';
      for (const card of cards.values()) card.querySelector('button').disabled = false;
    }
  }
  function boot() {
    if (started || !bridge()) return;
    started = true;
    el('voz-form')?.addEventListener('submit', event => {
      event.preventDefault();
      mutate('voz_criar', Number(el('voz-valor').value), el('voz-unidade').value);
    });
    el('voz-online-form').addEventListener('submit', event => {
      event.preventDefault();
      const token = el('voz-online-token').value;
      el('voz-online-token').value = '';
      mutate('voz_configurar_online', token, el('voz-online-enabled').checked);
    });
    el('voz-esfera').addEventListener('click', () => mutate('voz_escutar'));
    el('voz-microfone').addEventListener('click', () => mutate(snapshot.microfone ? 'voz_parar' : 'voz_iniciar'));
    const help = el('voz-ajuda');
    const tip = el('voz-ajuda-texto');
    const showHelp = open => { tip.hidden = !open; help.setAttribute('aria-expanded', String(open)); };
    const helpArea = el('voz-ajuda-area');
    let helpPinned = false, helpFocused = false;
    helpArea.addEventListener('mouseenter', () => showHelp(true));
    helpArea.addEventListener('mouseleave', () => { if (!helpPinned && !helpFocused) showHelp(false); });
    help.addEventListener('focus', () => { helpFocused = true; showHelp(true); });
    help.addEventListener('blur', () => { helpFocused = false; if (!helpPinned) showHelp(false); });
    help.addEventListener('click', () => { helpPinned = !helpPinned; showHelp(helpPinned); });
    help.addEventListener('keydown', event => { if (event.key === 'Escape') { helpPinned = false; showHelp(false); } });
    // Voz pausada (docs/voz-pausado.md): só lê o estado (Configurações mostra o acesso online salvo). Para religar, chame mutate('voz_iniciar') aqui e tire o hidden de #voz-pausado.
    refresh();
    setInterval(() => {
      countdown();
      if (el('page-voz').classList.contains('shown') || ++ciclo % 2 === 0) refresh(); // outras abas: a cada 2 s
    }, 1000);
  }
  window.vozLoad = refresh;
  if (typeof module !== 'undefined' && module.exports) module.exports = {format, render, boot, refresh};
  window.addEventListener('pywebviewready', boot);
  boot();
})();
