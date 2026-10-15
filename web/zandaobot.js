const ZB = {follow:true, world:'', serial:0};
const zbStamp = v => v ? new Date(v*1000).toLocaleString('pt-BR') : 'Não disponível';
const zbDate = v => /^\d{4}-\d{2}-\d{2}$/.test(v||'') ? v.split('-').reverse().join('/') : '—';
const zbLinks = {dream:'https://tibia.fandom.com/wiki/Dream_Scar/Boss_of_the_Day',yasir:'https://tibiatrade.gg/mini-world-changes',board:'https://www.tibiawiki.com.br/wiki/World_Board',calendar:'https://tibiacalendar.com/en/calendar'};
const zbLink = key => `<a href="${zbLinks[key]}" target="_blank" rel="noopener noreferrer">Abrir fonte ↗</a>`;
const zbDreamGifs = {'Maxxenius':'maxxenius','Alptramun':'alptramun','Izcandar the Banished':'izcandar-the-banished','Plagueroot':'plagueroot','Malofur Mangrinder':'malofur-mangrinder'};
function zbImageSrc(raw) {
  if(/^assets\/zandaobot\/[a-z-]+\.gif$/.test(raw||'')) return raw;
  try {
    const u=new URL(raw);
    if(u.protocol==='https:' && u.hostname==='static.tibia.com' && !u.username && !u.password && !u.search && !u.hash && /^\/images\/global\/header\/monsters\/[a-z0-9-]+\.gif$/.test(u.pathname)) return u.href;
  } catch(e) {}
  return '';
}
function zbSprite(src, label, icon) {
  const safe=zbImageSrc(src);
  return `<div class="zb-sprite"><span class="zb-sprite-fallback" ${safe?'hidden':''} aria-hidden="true">${icon}</span>${safe?`<img src="${esc(safe)}" alt="${esc(label)}" width="64" height="64" loading="eager">`:''}</div>`;
}
function zbDetails(key, data, text) {
  return `<details class="zb-source"><summary>Fonte e detalhes</summary><div><p>${esc(text||'')}</p><p>Consulta: ${esc(zbStamp(data.consulta))}${data.dia?' · '+esc(zbDate(data.dia)):''}</p>${key?zbLink(key):''}</div></details>`;
}
function zbCard(title, value, options={}) {
  const {kind='neutral', badge='', note='', sprite='', icon='•', details=''}=options;
  return `<article class="zb-tile zb-${kind}"><div class="zb-tile-heading"><h3>${esc(title)}</h3>${badge?`<span class="zb-badge">${esc(badge)}</span>`:''}</div><div class="zb-tile-content"><div class="zb-tile-text"><strong>${esc(value)}</strong>${note?`<p>${esc(note)}</p>`:''}</div>${zbSprite(sprite,value,icon)}</div>${details}</article>`;
}
function zbCalendar(c={}) {
  const stale=c.estado==='desatualizado';
  const groups=[['ativo','Em andamento'],['proximo','Próximos 60 dias']];
  return `<section class="zb-panel zb-calendar"><div class="zb-section-heading"><h2>Calendário de eventos</h2>${stale?'<span class="zb-badge zb-warning">Dados anteriores</span>':''}</div>${c.estado==='indisponivel'?'<p class="zb-warning-text">Calendário geral indisponível. Atualize para tentar novamente.</p>':''}<div class="zb-calendar-columns">${groups.map(([key,title])=>`<div><h3 class="zb-list-title">${title}</h3><div class="zb-event-list">${(c.eventos||[]).filter(e=>e.estado===key).map(e=>`<div class="zb-event"><span class="zb-event-dot ${key==='ativo'&&!stale?'zb-event-active':''}"></span><div><b>${esc(e.titulo)}</b><span>${esc(zbDate(e.inicio))} → ${esc(zbDate(e.fim))}</span><small>${esc(e.escopo)}${e.server_save?' · no server save':''}</small></div></div>`).join('')||`<p class="zb-empty">${c.estado==='indisponivel'?'Informação indisponível.':'Nenhum evento listado.'}</p>`}</div></div>`).join('')}</div><div class="zb-panel-footer"><span>Os eventos terminam no server save da data indicada.</span><details class="zb-source"><summary>Fonte do calendário</summary><div><p>Consulta: ${esc(zbStamp(c.consulta))}</p><p>${esc(c.nota||'')}</p>${zbLink('calendar')}</div></details></div></section>`;
}
function zbKillStatistics(k={}) {
  const available=k.estado==='disponivel'||k.estado==='desatualizado';
  const note=k.estado==='selecionar_mundo'?'Escolha um mundo para consultar as mortes registradas.':'Kill Statistics indisponível. Atualize para tentar novamente.';
  const source=/^[A-Za-z]{2,40}$/.test(k.mundo||'')?`https://www.tibia.com/community/?subtopic=killstatistics&world=${encodeURIComponent(k.mundo)}`:'';
  return `<details class="zb-kills"><summary>Mortes registradas · Kill Statistics${k.velho?' · dados anteriores':''}</summary>${available?`<table><caption>Bosses mortos por jogadores</caption><thead><tr><th scope="col">Boss</th><th scope="col">Last Day</th><th scope="col">Last Week</th></tr></thead><tbody>${(k.bosses||[]).map(b=>`<tr><th scope="row">${esc(b.nome)}</th><td>${Number.isInteger(b.last_day_killed)&&b.last_day_killed>=0?b.last_day_killed:'—'}</td><td>${Number.isInteger(b.last_week_killed)&&b.last_week_killed>=0?b.last_week_killed:'—'}</td></tr>`).join('')}</tbody></table><p>— = contagem indisponível; zero = nenhuma morte registrada.</p>`:`<p>${esc(note)}</p>`}<p>Last Day não equivale necessariamente ao último server save; não confirma o boss atual.</p>${k.velho?'<p class="zb-warning-text">Falha ao atualizar: exibindo a consulta anterior.</p>':''}<p>Consulta do aplicativo: ${esc(zbStamp(k.consulta))}<br>Processamento no TibiaData: ${esc(k.processamento?new Date(k.processamento).toLocaleString('pt-BR'):'Não informado')}</p>${source?`<a href="${esc(source)}" target="_blank" rel="noopener noreferrer">Estatísticas oficiais ↗</a>`:''}</details>`;
}

function zbRender(r) {
  if(r.erro) { $('zb-result').innerHTML=`<div class="zb-panel zb-warning-text">${esc(r.erro)}</div>`; return; }
  const b=r.boostados||{}, server=r.servidor||{}, dream=r.dream_court||{}, yasir=r.yasir||{}, world=r.mundo||'selecione um mundo';
  const boosted=(title,value,kind,icon)=>zbCard(title,value?.nome||'Indisponível',{kind,icon,sprite:value?.imagem,
    badge:b.velho?'Cache anterior':b.aguardando?'Aguardando fonte':'Hoje',note:b.velho?`Último dado: ${zbDate(b.dia)}`:b.aguardando?'Atualização após o server save pendente.':'Mesmo boost em todos os mundos.'});
  const globalCards=zbCard('Rashid',r.rashid||'Indisponível',{kind:'rashid',badge:'Hoje',note:'Localização do NPC neste dia.',sprite:'assets/zandaobot/rashid.gif',icon:'🐪'})
    +boosted('Criatura boostada',b.criatura,'creature','🐉')+boosted('Boss boostado',b.boss,'boss','⚔');
  const dreamBadge=dream.estado==='inconsistente'?'Consulta divergente':dream.velho?'Regras em cache':dream.incerto?'Rotação incerta':dream.estado==='selecionar_mundo'?'Selecione o mundo':dream.conferido?'Rotação conferida':'Rotação prevista';
  const dreamText=[dream.motivo,dream.conferido?'O boss foi conferido diretamente na resposta da TibiaWiki.':'',dream.atualizacao_fonte?`Revisão das regras: ${new Date(dream.atualizacao_fonte).toLocaleDateString('pt-BR')}.`:''].filter(Boolean).join(' ');
  const dreamSprite=zbDreamGifs[dream.nome]?'assets/zandaobot/'+zbDreamGifs[dream.nome]+'.gif':'';
  const dreamCard=zbCard('Dream Court',dream.nome||(dream.estado==='selecionar_mundo'?'Escolha um mundo':'Indisponível'),{kind:'dream',badge:dreamBadge,icon:'🌙',sprite:dreamSprite,
    note:dream.nome?`Rotação de hoje para ${world}.`:dream.motivo||'Atualize para consultar.',details:zbDetails('dream',dream,dreamText)+zbKillStatistics(r.killstatistics)});
  const yasirValue=yasir.estado==='presente'?'Presente':yasir.estado==='ausente'?'Ausente':yasir.estado==='desatualizado'?`Último registro: ${yasir.presente?'presente':'ausente'}`:yasir.estado==='inconsistente'?'Consulta divergente':yasir.estado==='selecionar_mundo'?'Escolha um mundo':'Indisponível';
  const yasirBadge=yasir.origem==='world_board_manual'?'World Board manual':yasir.velho?'Dados anteriores':yasir.estado==='presente'||yasir.estado==='ausente'?'Consulta atual':'Verificar';
  const yasirNote=yasir.estado==='presente'?(yasir.cidade||'Carlin, Ankrahmun ou Liberty Bay · cidade não informada.')
    :yasir.estado==='ausente'?`Não está listado em ${world} nesta consulta.`:yasir.motivo||'Atualize para consultar.';
  const yasirText=[yasir.motivo,yasir.conferido?'A lista de mundos e a consulta deste mundo concordam.':'',yasir.velho?`Registro anterior de ${zbDate(yasir.dia)}; situação atual não confirmada.`:'',yasir.origem==='world_board_manual'?'Observação manual do perfil. Pode mudar depois da consulta.':'A fonte não informa o horário de coleta no jogo.'].filter(Boolean).join(' ');
  const yasirCard=zbCard('Yasir',yasirValue,{kind:'yasir',badge:yasirBadge,note:yasirNote,icon:'⛵',sprite:'assets/zandaobot/yasir.gif',details:zbDetails(yasir.origem==='world_board_manual'?'board':'yasir',yasir,yasirText)});
  const worlds=yasir.mundos_com_yasir||[];
  const yasirWorlds=worlds.length?`<details class="zb-panel zb-worlds" ${!r.mundo?'open':''}><summary>Yasir em outros mundos <span>${worlds.length}${yasir.mundos_velhos?' · dados anteriores':''}</span></summary><div class="zb-world-buttons">${worlds.map(w=>`<button class="zb-world-button" data-zb-world="${esc(w)}">${esc(w)} ↗</button>`).join('')}</div></details>`:'';
  const changes=(yasir.mudancas||[]).filter(name=>name!=='Oriental Trader');
  const mini=changes.length?`<details class="zb-panel zb-extra"><summary>Mini World Changes em ${esc(world)} <span>${changes.length}${yasir.mudancas_velhas?' · consulta anterior':''}</span></summary><div class="zb-tags">${changes.map(name=>`<span class="zb-tag">${esc(name)}</span>`).join('')}</div></details>`:'';
  const alerts=r.avisos_mundo||[];
  const notice=alerts.length?`<section class="zb-panel zb-notice"><h2>Avisos de ${esc(world)}</h2>${r.avisos_mundo_velhos?'<p class="zb-warning-text">Alguns avisos não foram atualizados.</p>':''}${alerts.map(x=>`<p><small>${esc(zbDate(x.data))}</small> ${esc(x.texto)}${Number.isInteger(x.id)?` <a href="https://www.tibia.com/news/?subtopic=newsarchive&amp;id=${x.id}" target="_blank" rel="noopener noreferrer">Ler anúncio ↗</a>`:''}</p>`).join('')}</section>`:'';
  const announcements=`<details class="zb-panel zb-extra"><summary>Últimos anúncios oficiais</summary><p class="zb-muted">${r.anuncios_velhos?'Falha ao atualizar. ':''}Consulta: ${esc(zbStamp(r.anuncios_consulta))}</p>${(r.anuncios||[]).map(x=>`<p><small>${esc(zbDate(x.data))}</small> ${esc(x.titulo)}${Number.isInteger(x.id)?` <a href="https://www.tibia.com/news/?subtopic=newsarchive&amp;id=${x.id}" target="_blank" rel="noopener noreferrer">Ler ↗</a>`:''}</p>`).join('')||'<p class="zb-muted">Nenhum anúncio disponível.</p>'}</details>`;
  const online=server.name?`${server.players_online??'—'} jogadores · ${server.status==='online'?'online':server.status||'status desconhecido'}`:'Status indisponível';
  const save=new Date(r.server_save_ms).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
  const selectWorld=!r.mundo?`<div class="zb-panel zb-selection"><h2>Selecione o mundo de Tibia</h2><p>Yasir e Dream Court variam por mundo. Escolha abaixo ou pesquise no campo acima.</p><div class="zb-select-actions"><select id="zb-world-pick" aria-label="Selecionar mundo para Yasir e Dream Court"><option value="">Carregando mundos…</option></select><button class="zb-world-button" id="zb-config-world">Cadastrar personagem</button></div><small>Para usar o mundo automaticamente, cadastre e escolha seu personagem nas configurações desta instalação.</small></div>`:'';
  $('zb-result').innerHTML=`<div class="zb-overview"><div><span class="zb-eyebrow">RESUMO DIÁRIO</span><h2>${r.mundo?'Hoje em '+esc(world):'Resumo de hoje'}</h2></div><div class="zb-updated"><span>${esc(zbDate(r.dia))}</span><small>Consulta às ${esc(new Date(r.consulta).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'}))}</small></div></div><div class="zb-daily-grid">${globalCards}</div><div class="zb-section-heading zb-world-title"><h2>No mundo escolhido</h2><span class="zb-world-label">${esc(world)}</span></div>${selectWorld}<div class="zb-world-grid">${dreamCard}${yasirCard}</div><div class="zb-meta">${r.mundo?`<div><span>Mundo · ${esc(world)}</span><b>${esc(online)}</b><small>${esc(server.pvp_type||'')}${r.servidor_velho?' · dados anteriores':''}</small></div>`:''}<div><span>Próximo server save</span><b>${esc(save)}</b><small>Horário local</small></div></div>${yasirWorlds}${wbPanel(r)}${zbCalendar(r.calendario)}${notice}${mini}${announcements}`;
  wbBind(r);
  const picker=$('zb-world-pick');
  if(picker) {
    picker.onchange=()=>{if(picker.value){ZB.follow=false;ZB.world=picker.value;zbLoad();}};
    if(api&&typeof api.zandaobot_mundos==='function') api.zandaobot_mundos().then(data=>{
      if(!picker.isConnected)return;
      picker.innerHTML='<option value="">Escolha um mundo…</option>'+(data.mundos||[]).map(w=>`<option value="${esc(w)}">${esc(w)}</option>`).join('');
      if(!(data.mundos||[]).length)picker.innerHTML='<option value="">Digite o mundo no campo acima</option>';
    }).catch(()=>{if(picker.isConnected)picker.innerHTML='<option value="">Digite o mundo no campo acima</option>';});
    else picker.innerHTML='<option value="">Digite o mundo no campo acima</option>';
    $('zb-config-world').onclick=()=>{ZB.follow=true;if(typeof irPara==='function')irPara('config');};
  }
  $('zb-result').querySelectorAll('.zb-sprite img').forEach(img=>img.addEventListener('error',()=>{img.hidden=true;img.previousElementSibling.hidden=false;},{once:true}));
  $('zb-result').querySelectorAll('[data-zb-world]').forEach(btn=>btn.onclick=()=>{ZB.follow=false;ZB.world=btn.dataset.zbWorld;zbLoad();});
}
async function zbLoad(force=false) {
  if(!api) return;
  const world=ZB.follow?mundoAtual():ZB.world, serial=++ZB.serial;
  $('zb-world').value=world||'';
  $('zb-follow').textContent=ZB.follow?`Personagem em uso: ${MEUS.atual||'nenhum'} · ${world||'mundo não definido'}`:`Consulta independente: ${world}.`;
  $('zb-result').setAttribute('aria-busy','true');
  $('zb-refresh').disabled=true;
  $('zb-result').innerHTML='<div class="zb-panel zb-loading">Consultando informações de hoje…</div>';
  try {const r=await api.zandaobot_buscar(ZB.follow?'':world,force); if(serial===ZB.serial)zbRender(r);}
  catch(e) {if(serial===ZB.serial)$('zb-result').innerHTML='<div class="zb-panel zb-warning-text">Falha na consulta. Use Atualizar para tentar novamente.</div>';}
  finally {if(serial===ZB.serial){$('zb-result').setAttribute('aria-busy','false');$('zb-refresh').disabled=false;}}
}
$('zb-find').onclick=()=>{const world=$('zb-world').value.trim();if(!world){toast('Digite o mundo que deseja consultar.',true);return;}ZB.follow=false;ZB.world=world;zbLoad();};
$('zb-world').onkeydown=e=>{if(e.key==='Enter')$('zb-find').click();};
$('zb-active').onclick=()=>{ZB.follow=true;zbLoad();};
$('zb-refresh').onclick=()=>zbLoad(true);
$('zb-world').onfocus=async()=>{if(!api||$('zb-worlds').children.length)return;try{const r=await api.zandaobot_mundos();$('zb-worlds').innerHTML=(r.mundos||[]).map(w=>`<option value="${esc(w)}"></option>`).join('');}catch(e){}};
PERS_OUVINTES.push(()=>{if(!ZB.follow)return;ZB.serial++;if($('page-zandaobot').classList.contains('shown'))zbLoad();});
setInterval(()=>{if(api&&$('page-zandaobot').classList.contains('shown')&&!WB.dirty)zbLoad();},300000);
