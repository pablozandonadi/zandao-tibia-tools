/* Brasil Hits: um controlador persistente, sem scripts remotos ou Web Audio. */
class BrasilHitsPlayer {
  constructor({audioFactory = () => new Audio(), update = () => {}, timers = globalThis} = {}) {
    this.audioFactory = audioFactory; this.update = update; this.timers = timers;
    this.audio = null; this.wanted = false; this.url = ''; this.volume = .5;
    this.generation = 0; this.attempts = 0; this.retry = null; this.watch = null;
    this.state = 'parado';
  }
  status(state) { this.state = state; this.update(state); }
  release() {
    this.timers.clearTimeout(this.retry); this.timers.clearTimeout(this.watch);
    this.retry = this.watch = null;
    if (this.audio) { this.audio.pause(); this.audio.removeAttribute('src'); this.audio.load(); this.audio = null; }
  }
  stop() { this.wanted = false; this.generation++; this.release(); this.status('parado'); }
  setVolume(value) { this.volume = Math.max(0, Math.min(1, Number(value) || 0)); if (this.audio) this.audio.volume = this.volume; }
  play(url) {
    this.stop(); this.url = url; this.wanted = true; this.attempts = 0; this.connect();
  }
  connect() {
    this.generation++; const gen = this.generation;
    this.release(); if (!this.wanted) return;
    this.status(this.attempts ? 'reconectando' : 'conectando');
    const audio = this.audioFactory(); this.audio = audio; audio.volume = this.volume;
    const active = () => this.wanted && gen === this.generation && audio === this.audio;
    let lastTime = 0, lastProgress = Date.now();
    const arm = () => {
      this.timers.clearTimeout(this.watch);
      this.watch = this.timers.setTimeout(() => {
        if (!active()) return;
        if (audio.currentTime > lastTime) { lastTime = audio.currentTime; lastProgress = Date.now(); }
        if (Date.now() - lastProgress >= 20000) this.failed(gen);
        else arm();
      }, 5000);
    };
    audio.addEventListener('playing', () => { if (active()) { this.status('tocando'); lastProgress = Date.now(); } });
    audio.addEventListener('timeupdate', () => {
      if (active() && audio.currentTime > lastTime) {
        lastTime = audio.currentTime; lastProgress = Date.now();
        // Uma reprodução estável renova o orçamento; buffers curtos não criam loop infinito.
        if (audio.currentTime >= 30) this.attempts = 0;
      }
    });
    audio.addEventListener('error', () => { if (active()) this.failed(gen); });
    audio.addEventListener('ended', () => { if (active()) this.failed(gen); });
    audio.preload = 'none'; audio.src = this.url;
    arm();
    try { Promise.resolve(audio.play()).catch(error => {
      if (!active()) return;
      if (error && error.name === 'NotAllowedError') { this.stop(); this.status('clique para tocar'); }
      else this.failed(gen);
    }); } catch (_) { if (active()) this.failed(gen); }
  }
  failed(gen) {
    if (!this.wanted || gen !== this.generation) return;
    this.generation++; this.release();
    if (this.attempts >= 4) { this.wanted = false; this.status('indisponível'); return; }
    const delay = [2000, 5000, 10000, 20000][this.attempts++];
    this.status('reconectando');
    this.retry = this.timers.setTimeout(() => { if (this.wanted) this.connect(); }, delay);
  }
}

(function () {
  const el = id => document.getElementById(id);
  let stations = [], prefs = {channel: 'pop', quality: '', volume: 50};
  let loaded = false, loading = false, metaBusy = false, selection = 0, saveTimer;
  const labels = {parado: 'Parado', conectando: 'Conectando…', tocando: 'Ao vivo', reconectando: 'Reconectando…', 'indisponível': 'Rádio indisponível. Tente novamente.', 'clique para tocar': 'Clique em Tocar para iniciar.'};
  const player = new BrasilHitsPlayer({update(state) {
    el('radio-state').textContent = labels[state] || state;
    el('radio-toggle').textContent = player.wanted ? '■ Parar' : '▶ Tocar';
    el('radio-mini-toggle').textContent = player.wanted ? '■ Parar' : '▶ Tocar';
    el('radio-mini').hidden = !loaded;
  }});
  const bridge = () => window.pywebview && window.pywebview.api;
  const station = () => stations.find(s => s.id === prefs.channel);
  function save() {
    clearTimeout(saveTimer);
    const value = {...prefs};
    saveTimer = setTimeout(() => { const api = bridge(); if (api) api.radio_preferencias_salvar(value).catch(() => {}); }, 300);
  }
  function stream() {
    const s = station(); return s && ((s.qualities.find(q => q.id === prefs.quality) || {}).url || s.url);
  }
  function renderQualities() {
    const s = station(), select = el('radio-quality'); select.replaceChildren();
    select.add(new Option('Padrão', ''));
    for (const q of (s ? s.qualities : [])) select.add(new Option(q.label, q.id));
    if (!s || !s.qualities.some(q => q.id === prefs.quality)) prefs.quality = '';
    select.value = prefs.quality; select.disabled = !s || !s.qualities.length;
    el('radio-mini-channel').textContent = s ? 'Brasil Hits · ' + s.label : 'Brasil Hits';
    el('radio-toggle').disabled = !s || s.maintenance || !stream();
    el('radio-mini-toggle').disabled = el('radio-toggle').disabled;
    el('radio-song').textContent = s && s.maintenance ? 'Estação em manutenção' : 'Música atual disponível ao tocar';
  }
  async function metadata() {
    const api = bridge(), id = prefs.channel, gen = selection;
    if (!api || !player.wanted || metaBusy) return;
    metaBusy = true;
    try {
      const data = await api.radio_musica(id);
      if (gen !== selection || !player.wanted) return;
      el('radio-song').textContent = data.ok ? ([data.title, data.artist].filter(Boolean).join(' — ') || 'Brasil Hits ao vivo') : 'Informações da música indisponíveis';
    } catch (_) { if (gen === selection && player.wanted) el('radio-song').textContent = 'Informações da música indisponíveis'; }
    finally { metaBusy = false; }
  }
  function toggle() {
    if (player.wanted) { player.stop(); selection++; return; }
    const s = station(), url = stream();
    if (!s || s.maintenance || !url) return;
    player.play(url); selection++; metadata();
  }
  window.radioLoad = async function () {
    if (loading || !bridge()) return;
    loading = true; el('radio-message').textContent = 'Carregando estações…';
    try {
      const [catalog, saved] = await Promise.all([bridge().radio_catalogo(), bridge().radio_preferencias()]);
      if (!catalog.ok) throw new Error(catalog.error);
      stations = catalog.stations;
      if (!loaded) prefs = saved;
      if (!station()) prefs.channel = stations[0].id;
      const select = el('radio-channel'); select.replaceChildren();
      for (const s of stations) select.add(new Option(s.label + (s.maintenance ? ' · manutenção' : ''), s.id));
      select.value = prefs.channel; el('radio-volume').value = prefs.volume;
      player.setVolume(prefs.volume / 100); renderQualities(); loaded = true;
      el('radio-mini').hidden = false;
      el('radio-message').textContent = catalog.stale ? 'Usando o catálogo anterior. A conexão será verificada novamente.' : 'Escolha um canal e toque. O volume da rádio é independente dos timers.';
    } catch (error) { el('radio-message').textContent = error.message || 'Não foi possível carregar as rádios.'; }
    finally { loading = false; }
  };
  el('radio-channel').addEventListener('change', () => {
    const resume = player.wanted; player.stop(); selection++;
    prefs.channel = el('radio-channel').value; prefs.quality = ''; renderQualities(); save();
    if (resume) toggle();
  });
  el('radio-quality').addEventListener('change', () => {
    const resume = player.wanted; player.stop(); selection++;
    prefs.quality = el('radio-quality').value; save(); if (resume) toggle();
  });
  el('radio-volume').addEventListener('input', () => { prefs.volume = Number(el('radio-volume').value); player.setVolume(prefs.volume / 100); save(); });
  el('radio-toggle').addEventListener('click', toggle);
  el('radio-mini-toggle').addEventListener('click', toggle);
  el('radio-reload').addEventListener('click', window.radioLoad);
  el('radio-mini-open').addEventListener('click', () => irPara('radio'));
  el('radio-site').addEventListener('click', () => { if (bridge()) bridge().radio_abrir_site(); });
  setInterval(metadata, 15000);
  window.addEventListener('beforeunload', () => player.stop());
})();
