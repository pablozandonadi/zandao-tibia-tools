async function iniciarPublicacaoBeta() {
  const painel = document.getElementById('beta-publicacao');
  const botao = document.getElementById('beta-publicar-original');
  const status = document.getElementById('beta-publicacao-status');
  const link = document.getElementById('beta-publicacao-link');
  let info;
  try { info = await api.beta_publicacao_info(); } catch (_) { return; }
  if (!info.beta) return;
  painel.style.display = 'block';
  document.getElementById('beta-publicacao-info').textContent = info.mensagem;
  botao.disabled = !info.disponivel;
  function mostrarLink(url, texto) {
    if (!url) return;
    link.href = url; link.textContent = texto; link.style.display = 'inline';
  }
  link.addEventListener('click', (event) => {
    event.preventDefault(); api.beta_publicacao_abrir(link.href);
  });
  async function acompanhar() {
    try {
      const resultado = await api.beta_publicacao_estado();
      status.textContent = resultado.mensagem || resultado.erro;
      if (!resultado.ok) { botao.disabled = false; return; }
      mostrarLink(resultado.release_url || resultado.url,
                  resultado.status === 'concluido' ? 'Ver versão publicada' : 'Acompanhar publicação');
      if (resultado.status === 'falhou') { botao.disabled = false; return; }
      if (resultado.status === 'concluido') { botao.textContent = 'Versão original publicada'; return; }
      setTimeout(acompanhar, 15000);
    } catch (_) {
      status.textContent = 'Não foi possível acompanhar agora. Confira a publicação pelo link antes de tentar novamente.';
      botao.disabled = false;
    }
  }
  botao.addEventListener('click', async () => {
    if (!confirm(`Você aprovou a Beta ${info.versao}? Publicar esta versão para todos os usuários da versão original, incluindo o instalador?`)) return;
    botao.disabled = true; status.textContent = 'Solicitando publicação…';
    try {
      const resultado = await api.beta_publicar_original();
      status.textContent = resultado.mensagem || resultado.erro;
      if (!resultado.ok) { botao.disabled = false; return; }
      mostrarLink(resultado.url, 'Acompanhar publicação');
      setTimeout(acompanhar, 5000);
    } catch (_) {
      status.textContent = 'Não foi possível confirmar a solicitação. Confira o pipeline antes de tentar novamente.';
      botao.disabled = false;
    }
  });
}
