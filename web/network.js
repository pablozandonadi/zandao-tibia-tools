/* Rede: bounded SVG charts; network collection lives in Python, including while minimized. */
(() => {
  const root = document.getElementById('page-rede');
  if (!root) return;
  const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const colors = ['#46dfb1','#7eb7ff','#efb65b','#da94f5','#fb879e','#a8d367','#81e5ef','#cbb8a3'];
  let data, windowSeconds = 300, busy = false, showAll = false;
  const ms = x => x == null ? '—' : `${Math.round(x)} <small>ms</small>`;
  const bytes = n => { if (n == null) return 'Indisponível'; const unit = Math.min(3, Math.floor(Math.log(Math.max(1,n))/Math.log(1000))); return `${unit ? (n/1000**unit).toLocaleString('pt-BR',{maximumFractionDigits:2}) : n} ${['B','KB','MB','GB'][unit]}`; };
  const duration = n => { n = Math.floor(n || 0); return n >= 3600 ? `${Math.floor(n/3600)}h ${Math.floor(n%3600/60)}min` : n >= 60 ? `${Math.floor(n/60)}min ${n%60}s` : `${n}s`; };
  const time = x => x ? new Date(x*1000).toLocaleTimeString('pt-BR') : '—';
  root.innerHTML = `<div class="net-heading"><div><div class="net-eyebrow">CONEXÕES EM TEMPO REAL</div><h1 class="titulo">Sua rede, à vista</h1><p class="dica">Veja cada internet separadamente, mesmo com as duas conectadas.</p></div><button class="btn btn-primary" id="net-toggle">Iniciar monitoramento</button></div>
    <div id="net-summary" class="net-summary" role="status">Consultando adaptadores…</div>
    <div class="net-controls"><span>Leitura a cada 1 segundo · ping alto acima de 100 ms</span><label><input id="net-sound" type="checkbox"> Som de conexão</label><label><input id="net-notifications" type="checkbox"> Avisos de conexão</label><label><input id="net-show-all" type="checkbox"> Outros adaptadores</label></div>
    <div id="net-error" role="alert"></div><div id="net-cards" class="net-cards"></div>
    <section class="net-panel"><h2 class="sub">Resumo do período monitorado</h2><p class="dica">Totais desde o início da coleta nesta execução · não são limitados aos últimos pontos do gráfico. Envio e recebimento incluem todos os programas de cada adaptador; pausas não entram no total.</p><div id="net-session" class="net-session"></div></section>
    <section class="net-panel"><div class="net-heading"><div><h2 class="sub">Variação da latência</h2><p class="dica">TCP · Cloudflare · falhas interrompem a linha</p></div><label>Janela <select id="net-window"><option value="300">5 minutos</option><option value="3600">1 hora</option><option value="86400">24 horas</option></select></label></div><div id="net-legend" class="net-legend"></div><div id="net-chart"></div><div class="net-chart-foot"><span id="net-chart-start"></span><span>Agora</span></div></section>
    <section class="net-panel"><h2 class="sub">O que aconteceu</h2><p class="dica">Eventos desta sessão · até 200 registros</p><div id="net-events" aria-live="off"></div></section>
    <p class="net-note">As sondas usam a interface escolhida e verificam dois destinos externos. Latência TCP não é o ping do Tibia; perda representa falhas das sondas. A rota utilizada pelo ExitLag não é identificada por este painel. A coleta usa dados de cada conexão, inclusive do celular.</p>
    <details class="net-note"><summary>Como interpretar</summary><p>Conectado: há resposta externa pela própria interface, independentemente do ping. Desconectado: o cabo/USB foi retirado ou os dois destinos falharam em duas leituras seguidas. Verificando: confirmação em andamento. Medição indisponível: erro ao testar a interface, sem conclusão sobre a operadora. Os avisos e sons indicam apenas conectado ou desconectado.</p><p>A leitura ocorre a cada 1 segundo. O resumo acumula o período inteiro desta execução; tempo sem coleta, pausa ou suspensão não é contado. Média e maior latência usam Cloudflare; o limite de 100 ms é acompanhado nos dois destinos. Timeouts e falhas são das sondas TCP, não contagem de pacotes do Tibia. Episódios acima de 100 ms são registrados automaticamente no histórico com pico e número de leituras, sem som nem notificação. Os testes são IPv4; uma rede somente IPv6 não é avaliada nesta versão. Estatísticas dos últimos 900 pontos. Gráficos longos usam agregados por minuto. Histórico fica na memória desta sessão.</p></details>`;
  function graph(links, now, seconds, small = false) {
    const w = small ? 400 : 1000, h = small ? 75 : 240, pad = small ? 5 : 38;
    const all = links.flatMap(l => l.points).map(p => p.ms).filter(x => x != null);
    const max = Math.max(80, ...all) * 1.15;
    const x = t => pad+(t-(now-seconds))/seconds*(w-pad-8);
    const y = n => h-18-n/max*(h-32);
    let svg = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Gráfico de latência TCP por conexão"><title>Latência TCP em milissegundos; lacunas indicam ausência de resposta ou coleta.</title>`;
    if (!small) for (let n=0;n<=4;n++) { const v=max*n/4; svg+=`<line x1="${pad}" x2="${w}" y1="${y(v)}" y2="${y(v)}" class="net-grid"/><text x="0" y="${y(v)+4}" class="net-axis">${Math.round(v)}</text>`; }
    links.forEach(l => {
      const points = l.points.filter(p=>p.t >= now-seconds);
      let path = '', pen = false, last = 0;
      // Each display bucket preserves gaps and peak rather than averaging away spikes.
      const buckets = new Map();
      points.forEach(p=> { const k=Math.floor((p.t-(now-seconds))/seconds*300); const b=buckets.get(k); if(!b) buckets.set(k,{...p}); else { b.t=p.t; b.ms=b.ms==null||p.ms==null?null:Math.max(b.ms,p.ms); b.loss=p.loss==null?b.loss:Math.max(b.loss||0,p.loss); } });
      for(const p of buckets.values()) {
        if(p.ms==null) { pen=false; if(p.loss>0) svg+=`<line x1="${x(p.t)}" x2="${x(p.t)}" y1="${h-15}" y2="${h-4}" stroke="${l.color}" stroke-width="2"><title>${esc(l.alias)} · falha na sonda</title></line>`; continue; }
        const gap = p.t-last > (seconds>900?130:Math.max(8,(data?.config.interval||2)*3));
        path += `${pen&&!gap?'L':'M'}${x(p.t).toFixed(1)},${y(p.ms).toFixed(1)} `; pen=true; last=p.t;
      }
      svg+=`<path d="${path}" stroke="${l.color}" stroke-width="${small?2:2.5}" fill="none" stroke-linejoin="round"/>`;
    });
    if(!all.length) svg+=`<text x="${w/2}" y="${h/2}" text-anchor="middle" class="net-axis">Aguardando respostas nesta janela</text>`;
    return svg+'</svg>';
  }
  function render(d) {
    data=d;
    d.links.forEach((l,i)=>l.color=colors[i%colors.length]);
    document.getElementById('net-toggle').textContent=d.config.enabled?'Pausar monitoramento':'Iniciar monitoramento';
    for(const key of ['sound','notifications']) document.getElementById('net-'+key).checked=d.config[key];
    const summary=document.getElementById('net-summary');
    const connected=d.links.filter(l=>l.selected && l.connected===true).length;
    let text=!d.config.enabled?'Monitoramento pausado':connected>=2?`${connected} conexões conectadas · redundância disponível`:connected===1?'Uma conexão conectada · sem redundância confirmada':d.links.some(l=>l.selected && l.connected==null)?'Verificando conexões…':'Todas as conexões selecionadas estão desconectadas';
    if(!d.links.length) text='Nenhum adaptador encontrado · aguardando nova consulta';
    if(d.error) text='Monitoramento indisponível · resultados anteriores não confirmam o estado atual';
    summary.textContent=text; summary.dataset.ok=connected>=2&&d.config.enabled&&!d.error?'yes':'no';
    document.getElementById('net-error').textContent=d.error||'';
    const cards=document.getElementById('net-cards');
    const focused=document.activeElement;
    const edit=cards.contains(focused)&&focused.matches('[data-net-alias]')?{id:focused.dataset.netAlias,value:focused.value,start:focused.selectionStart,end:focused.selectionEnd}:null;
    const open=new Set([...cards.querySelectorAll('details[open]')].map(x=>x.closest('article').dataset.netId));
    cards.innerHTML=d.links.filter(l=>l.selected||showAll).map(l=>`<article class="net-link" data-net-id="${esc(l.id)}" style="--link-color:${l.color}"><div class="net-link-head"><label class="net-select"><input type="checkbox" data-net-select="${esc(l.id)}" ${l.selected?'checked':''} aria-label="Monitorar ${esc(l.alias)}"><b>${esc(l.alias)}</b></label><span class="net-state net-${esc(l.state)}">${esc(l.label)}</span></div><p class="net-device">${esc(l.description)}${l.virtual?' · Virtual':''}</p><div class="net-current">${ms(l.current)}<span>Latência TCP agora</span></div><div class="net-mini">${graph([l],d.now,Math.min(windowSeconds,900),true)}</div><div class="net-metrics"><div>Média<b>${ms(l.average)}</b></div><div>Falhas de sondas<b>${l.loss==null?'—':l.loss+'%'}</b></div><div>Jitter<b>${ms(l.jitter)}</b></div><div>Maior / p95<b>${l.maximum==null?'—':Math.round(l.maximum)+' / '+Math.round(l.p95)+' ms'}</b></div></div><div class="net-stability">${l.connected===true?'✓ Conectado há '+duration(l.connected_for):'Última resposta: '+time(l.last_success)}</div><details><summary>Identificar conexão</summary><label>Apelido<input type="text" data-net-alias="${esc(l.id)}" maxlength="60" value="${esc(l.alias)}"></label><label><input type="radio" name="net-preferred" data-net-preferred="${esc(l.id)}" ${d.config.preferred===l.id?'checked':''}> Minha preferida</label></details>${d.config.preferred===l.id?'<span class="net-preferred">★ Sua preferida</span>':''}</article>`).join('');
    for(const article of cards.querySelectorAll('article')) {
      if(open.has(article.dataset.netId)) article.querySelector('details').open=true;
      if(edit && article.dataset.netId===edit.id) {
        const field=article.querySelector('[data-net-alias]');field.value=edit.value;field.focus({preventScroll:true});field.setSelectionRange(edit.start,edit.end);
      }
    }
    const visible=d.links.filter(l=>l.selected);
    document.getElementById('net-session').innerHTML=visible.map(l=>{
      const t=l.totals||{}, traffic=l.traffic||{};
      return `<article class="net-session-link"><h3 style="color:${l.color}">${esc(l.alias)}</h3><p class="dica">Desde ${time(t.since)} · ${duration(t.observed_seconds)} observados</p><div class="net-metrics"><div>Enviado na sessão<b>${bytes(traffic.sent)}</b></div><div>Recebido na sessão<b>${bytes(traffic.received)}</b></div><div>Média / maior latência<b>${t.average==null?'—':Math.round(t.average)+' / '+Math.round(t.maximum)+' ms'}</b></div><div>Acima de 100 ms<b>${t.high_readings||0} de ${t.readings||0} leituras (${t.high_percent||0}%)</b></div><div>Tempo com ping alto<b>${duration(t.high_seconds)} · ${t.high_episodes||0} episódios</b></div><div>Timeouts<b>${t.timeouts||0}</b></div><div>Falhas das sondas<b>${t.failures||0} / ${t.attempts||0} (${t.failure_percent||0}%)</b></div><div>Quedas / desconectado<b>${t.outages||0} · ${duration(t.disconnected_seconds)}</b></div><div>Tempo conectado<b>${duration(t.connected_seconds)}</b></div><div>Falhas de medição<b>${t.measurement_errors||0}</b></div></div>${traffic.received!=null && (!traffic.available || traffic.partial)?`<p class="dica">${!traffic.available?'Leitura de tráfego indisponível. ':''}Totais parciais: houve intervalo sem medição de tráfego.</p>`:''}</article>`;
    }).join('');
    document.getElementById('net-legend').innerHTML=visible.map(l=>`<span style="color:${l.color}">● ${esc(l.alias)}</span>`).join('');
    document.getElementById('net-chart').innerHTML=graph(visible,d.now,windowSeconds);
    document.getElementById('net-chart-start').textContent=time(d.now-windowSeconds);
    document.getElementById('net-events').innerHTML=d.events.length?d.events.slice(0,50).map(e=>`<div class="net-event"><time>${time(e.t)}</time><span class="net-state net-${esc(e.state)}">${esc(e.message)}</span></div>`).join(''):'<p class="dica">Os eventos aparecem aqui quando o estado de uma conexão muda.</p>';
  }
  async function update(changes) {
    try { const d=await window.pywebview.api.rede_configurar(changes); if(d.error_config) throw new Error(d.error_config); await load(); }
    catch(e) { document.getElementById('net-error').textContent=e.message||'Não foi possível salvar a configuração.'; }
  }
  async function load() {
    if(busy||!root.classList.contains('shown')||!window.pywebview?.api) return;
    busy=true;
    try { render(await window.pywebview.api.rede_estado(windowSeconds)); }
    catch(e) { document.getElementById('net-error').textContent='Não foi possível consultar o monitor. Tente abrir a seção novamente.'; }
    finally { busy=false; }
  }
  document.getElementById('net-show-all').onchange=e=>{showAll=e.target.checked;load();};
  document.getElementById('net-toggle').onclick=()=>data&&update({enabled:!data.config.enabled});
  document.getElementById('net-window').onchange=e=>{windowSeconds=Number(e.target.value);load();};
  for(const key of ['sound','notifications']) document.getElementById('net-'+key).onchange=e=>update({[key]:e.target.checked});
  root.addEventListener('change',e=> {
    if(!data) return;
    if(e.target.dataset.netSelect) {
      const ids=new Set(data.config.excluded), id=e.target.dataset.netSelect;
      if(e.target.checked) { if(data.selected>=data.limit) {e.target.checked=false;document.getElementById('net-error').textContent=`Selecione até ${data.limit} conexões.`;return;} ids.delete(id); } else ids.add(id);
      update({excluded:[...ids]});
    }
    if(e.target.dataset.netAlias) update({aliases:{...data.config.aliases,[e.target.dataset.netAlias]:e.target.value}});
    if(e.target.dataset.netPreferred) update({preferred:e.target.dataset.netPreferred});
  });
  new MutationObserver(()=>load()).observe(root,{attributes:true,attributeFilter:['class']});
  setInterval(load,500);
})();
