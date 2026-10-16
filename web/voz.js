(function () {
  'use strict';
  let snapshot = {timers: []}, received = 0, started = false, busy = false;
  const cards = new Map();
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
    el('voz-ouvi').textContent = data.ouvi || 'Aguardando “Hey Tibia Tudo”.';
    el('voz-resposta').textContent = data.resposta || 'As respostas aparecerão aqui, tibiano.';
    el('voz-microfone').textContent = data.microfone ? 'Pausar microfone' : (data.estado === 'erro' ? 'Tentar novamente' : 'Retomar microfone');
    el('voz-microfone').disabled = busy;
    const ids = new Set((data.timers || []).map(timer => timer.id));
    for (const [id, card] of cards) {
      if (!ids.has(id)) { card.remove(); cards.delete(id); }
    }
    for (const timer of data.timers || []) {
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
    el('voz-vazio').hidden = ids.size > 0;
    el('voz-quantidade').textContent = `${ids.size} ${ids.size === 1 ? 'timer ativo' : 'timers ativos'}`;
    countdown();
  }
  async function refresh() {
    if (!bridge() || busy) return;
    busy = true;
    try {
      const data = await bridge().voz_estado();
      if (data.erro) throw new Error(data.erro);
      render(data);
    } catch (error) { el('voz-feedback').textContent = error.message || 'Não consegui consultar os timers.'; }
    finally {
      busy = false;
      el('voz-microfone').disabled = false;
      for (const card of cards.values()) card.querySelector('button').disabled = false;
    }
  }
  async function mutate(method, ...args) {
    if (!bridge() || busy) return;
    busy = true;
    el('voz-feedback').textContent = '';
    el('voz-criar').disabled = true;
    try {
      const data = await bridge()[method](...args);
      if (data.erro) throw new Error(data.erro);
      render(data);
    } catch (error) { el('voz-feedback').textContent = error.message || 'Não consegui concluir o comando, tibiano.'; }
    finally {
      busy = false;
      el('voz-criar').disabled = false;
      el('voz-microfone').disabled = false;
      for (const card of cards.values()) card.querySelector('button').disabled = false;
    }
  }
  function boot() {
    if (started || !bridge()) return;
    started = true;
    el('voz-form').addEventListener('submit', event => {
      event.preventDefault();
      mutate('voz_criar', Number(el('voz-valor').value), el('voz-unidade').value);
    });
    el('voz-microfone').addEventListener('click', () => mutate(snapshot.microfone ? 'voz_parar' : 'voz_iniciar'));
    mutate('voz_iniciar');
    setInterval(() => {
      countdown();
      if (el('page-voz').classList.contains('shown')) refresh();
    }, 1000);
  }
  window.vozLoad = refresh;
  if (typeof module !== 'undefined' && module.exports) module.exports = {format, render, boot, refresh};
  window.addEventListener('pywebviewready', boot);
  boot();
})();
