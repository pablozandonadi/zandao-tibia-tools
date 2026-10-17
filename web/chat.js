(function () {
  'use strict';
  let busy = false, started = false;
  const el = id => document.getElementById(id);
  const bridge = () => window.pywebview && window.pywebview.api;
  // Tudo entra por textContent: a resposta pode vir da IA e nunca é interpretada como HTML.
  function render(classe, texto, entendi) {
    const balao = document.createElement('div');
    balao.className = classe;
    const fala = document.createElement('p');
    fala.textContent = texto;
    balao.append(fala);
    if (entendi && entendi !== '—') {
      const nota = document.createElement('small');
      nota.textContent = `Entendi: ${entendi}`;
      balao.append(nota);
    }
    const caixa = el('chat-mensagens');
    caixa.append(balao);
    caixa.scrollTop = caixa.scrollHeight;
    return balao;
  }
  async function enviar(texto) {
    const botao = el('chat-form').querySelector('button[type=submit]');
    busy = true;
    botao.disabled = true;
    render('chat-eu', texto);
    try {
      if (!bridge()) throw new Error('O aplicativo ainda está carregando. Tente de novo em instantes.');
      const dados = await bridge().assistente_chat(texto);
      if (dados.erro) throw new Error(dados.erro);
      render('chat-bot', dados.resposta, dados.entendi);
    } catch (error) { render('chat-bot chat-erro', error.message || 'Não consegui responder agora.'); }
    finally { busy = false; botao.disabled = false; el('chat-texto').focus(); }
  }
  async function limpar() {
    try {
      if (!bridge()) throw new Error('O aplicativo ainda está carregando.');
      await bridge().assistente_chat_limpar();
      el('chat-mensagens').replaceChildren();
    } catch (error) { render('chat-bot chat-erro', error.message || 'Não consegui limpar a conversa.'); }
  }
  function boot() {
    if (started) return;
    started = true;
    el('chat-form').addEventListener('submit', event => {
      event.preventDefault();
      const texto = el('chat-texto').value.trim();
      if (!texto || busy) return;
      el('chat-texto').value = '';
      enviar(texto);
    });
    el('chat-limpar').addEventListener('click', limpar);
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {render, enviar, limpar, boot};
  boot();
})();
