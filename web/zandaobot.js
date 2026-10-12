const ZB = {follow:true, world:'', serial:0};
const zbStamp = v => v ? new Date(v*1000).toLocaleString('pt-BR') : 'sem consulta disponível';
const zbDate = v => /^\d{4}-\d{2}-\d{2}$/.test(v||'') ? v.split('-').reverse().join('/') : '—';
const zbLinks = {dream:'https://tibia.fandom.com/wiki/Dream_Scar/Boss_of_the_Day',yasir:'https://tibiatrade.gg/mini-world-changes',calendar:'https://tibiacalendar.com/en/calendar'};
const zbLink = key => `<a href="${zbLinks[key]}" target="_blank" rel="noopener noreferrer">Ver fonte ↗</a>`;
function zbCard(title, value, detail='', color='var(--accent)', footer='') {
  return `<div class="card calmo zb-card" style="border-left-color:${color}"><h2 class="sub">${esc(title)}</h2><strong>${esc(value)}</strong><p class="dica">${esc(detail)}</p>${footer?`<p class="dica">${footer}</p>`:''}</div>`;
}
function zbCalendar(c={}) {
  const stale=c.estado==='desatualizado';
  const events=c.eventos||[];
  const groups=[['ativo','Em andamento'],['proximo','Próximos 60 dias']];
  return `<div class="card calmo zb-calendar"><div class="zb-heading"><h2 class="sub">Calendário de eventos</h2>${zbLink('calendar')}</div><p class="dica">${esc(c.nota||'Não foi possível consultar o calendário. Tente atualizar novamente.')}</p><p class="dica">Consulta: ${esc(zbStamp(c.consulta))}${stale?' · Falha ao atualizar: exibindo o calendário anterior.':''}</p>${groups.map(([key,title])=>`<h3>${title}</h3><div class="zb-events">${events.filter(e=>e.estado===key).map(e=>`<div class="zb-event"><span class="zb-chip ${key==='ativo'&&!stale?'zb-chip-active':''}">${stale?'Cache anterior':key==='ativo'?'Em andamento':'Próximo'}</span><b>${esc(e.titulo)}</b><span>${esc(zbDate(e.inicio))} → ${esc(zbDate(e.fim))}${e.server_save?' · server save':''}</span><span class="dica">${esc(e.escopo)}</span></div>`).join('')||`<p class="dica">${c.estado==='indisponivel'?'Informação indisponível.':'Nenhum evento listado neste período.'}</p>`}</div>`).join('')}<p class="dica">O dia do Tibia muda no server save. Eventos que terminam hoje no server save já não aparecem como ativos.</p></div>`;
}
function zbRender(r) {
  if(r.erro) { $('zb-result').innerHTML=zbCard('Consulta',r.erro); return; }
  const b=r.boostados||{}, server=r.servidor||{}, dream=r.dream_court||{}, yasir=r.yasir||{};
  const boosted=(title, value)=>zbCard(title,value?.nome||'Indisponível',b.velho?`Dados anteriores · ${b.dia}. Falha ao atualizar.`:b.aguardando?'Aguardando a fonte atualizar após o server save.':'Global · igual para todos os mundos.');
  let cards=zbCard('Rashid',r.rashid,'Global · localização muda no server save.','#e3b45b')+boosted('Criatura boostada',b.criatura)+boosted('Boss boostado',b.boss);
  const dreamValue=dream.nome?`${dream.nome} · ${dream.velho?'regras em cache':'previsto'}`:'Indisponível';
  const dreamDetail=[dream.motivo,dream.atualizacao_fonte?`Regras atualizadas na fonte: ${new Date(dream.atualizacao_fonte).toLocaleString('pt-BR')}.`:'',dream.velho?'Falha ao atualizar a rotação.':''].filter(Boolean).join(' ');
  cards+=zbCard('Dream Court · '+(r.mundo||'selecione um mundo'),dreamValue,dreamDetail,'#ad85ed',`${zbLink('dream')} · Consulta: ${esc(zbStamp(dream.consulta))}`);
  const yasirValue=yasir.estado==='presente'?'Presente no mundo':yasir.estado==='ausente'?'Ausente na consulta':yasir.estado==='desatualizado'?`Última consulta: ${yasir.presente?'presente':'ausente'}`:'Indisponível';
  const yasirDetail=[yasir.motivo,yasir.estado==='desatualizado'?`Dados anteriores de ${zbDate(yasir.dia)}; presença atual não confirmada.`:'',yasir.consulta?'A fonte não informa o horário de coleta no jogo.':''].filter(Boolean).join(' ');
  cards+=zbCard('Yasir · '+(r.mundo||'selecione um mundo'),yasirValue,yasirDetail,'#46c9bb',`${zbLink('yasir')} · Consulta: ${esc(zbStamp(yasir.consulta))}`);
  cards+=zbCard('Próximo server save',new Date(r.server_save_ms).toLocaleString('pt-BR'),'Horário local deste computador.');
  if(r.mundo) cards+=zbCard('Mundo · '+r.mundo,server.name?`${server.status==='online'?'Online':server.status||'Status indisponível'} · ${server.players_online??'—'} jogadores`:'Informações indisponíveis',`${server.location||''} · ${server.pvp_type||''} · Consulta: ${zbStamp(r.servidor_consulta)}${r.servidor_velho?' · Cache anterior / falha ao atualizar':''}`);
  const changes=(yasir.mudancas||[]).filter(name=>name!=='Oriental Trader');
  const mini=changes.length?`<div class="card calmo zb-calendar"><h2 class="sub">Outras Mini World Changes · ${esc(r.mundo)}</h2><p class="dica">${yasir.velho?'Consulta anterior · ':''}${esc(zbStamp(yasir.consulta))}</p><div class="zb-tags">${changes.map(name=>`<span class="zb-chip">${esc(name)}</span>`).join('')}</div></div>`:'';
  const alerts=r.avisos_mundo||[];
  const notice=alerts.length?`<div class="card calmo zb-calendar"><h2 class="sub">Avisos oficiais · ${esc(r.mundo)}</h2><p class="dica">Anúncios específicos deste mundo podem incluir eventos de compensação. ${r.avisos_mundo_velhos?'Falha ao atualizar os avisos.':''}</p>${alerts.map(x=>`<p><span class="dica">${esc(x.data)}</span> · ${esc(x.texto)}</p>`).join('')}</div>`:'';
  const announcements=`<details class="card calmo zb-calendar"><summary>Últimos anúncios oficiais</summary><p class="dica">A data é a publicação. ${r.anuncios_velhos?'Falha ao atualizar os anúncios. ':''}Consulta: ${esc(zbStamp(r.anuncios_consulta))}</p>${(r.anuncios||[]).map(x=>`<p><span class="dica">${esc(x.data)}</span> · ${esc(x.titulo)}${Number.isInteger(x.id)?` <a href="https://www.tibia.com/news/?subtopic=newsarchive&amp;id=${x.id}" target="_blank" rel="noopener noreferrer">Ler anúncio ↗</a>`:''}</p>`).join('')||'<p class="dica">Nenhum anúncio disponível nesta consulta.</p>'}<a href="https://www.tibia.com/news/?subtopic=eventcalendar" target="_blank" rel="noopener noreferrer">Calendário oficial ↗</a></details>`;
  $('zb-result').innerHTML=`<div class="zb-heading"><h2 class="sub">Dia do Tibia · ${esc(zbDate(r.dia))}</h2><span class="dica">Consulta: ${esc(new Date(r.consulta).toLocaleString('pt-BR'))}</span></div><div class="zb-grid">${cards}</div>${zbCalendar(r.calendario)}${notice}${mini}${announcements}`;
}
async function zbLoad(force=false) {
  if(!api) return;
  const world=ZB.follow?mundoAtual():ZB.world, serial=++ZB.serial;
  $('zb-world').value=world||'';
  $('zb-follow').textContent=ZB.follow?`Personagem em uso: ${MEUS.atual||'nenhum'} · Mundo: ${world||'não definido'}`:`Consultando o mundo ${world}.`;
  $('zb-result').innerHTML='<div class="card dica">Consultando informações do dia…</div>';
  try {const r=await api.zandaobot_buscar(ZB.follow?'':world,force); if(serial===ZB.serial)zbRender(r);}
  catch(e) {if(serial===ZB.serial)$('zb-result').innerHTML=zbCard('Consulta','Falha ao consultar. Tente atualizar.');}
}
$('zb-find').onclick=()=>{const world=$('zb-world').value.trim();if(!world){toast('Digite o mundo que deseja consultar.',true);return;}ZB.follow=false;ZB.world=world;zbLoad();};
$('zb-world').onkeydown=e=>{if(e.key==='Enter')$('zb-find').click();};
$('zb-active').onclick=()=>{ZB.follow=true;zbLoad();};
$('zb-refresh').onclick=()=>zbLoad(true);
$('zb-world').onfocus=async()=>{if(!api||$('zb-worlds').children.length)return;try{const r=await api.zandaobot_mundos();$('zb-worlds').innerHTML=(r.mundos||[]).map(w=>`<option value="${esc(w)}"></option>`).join('');}catch(e){}};
PERS_OUVINTES.push(()=>{if(!ZB.follow)return;ZB.serial++;if($('page-zandaobot').classList.contains('shown'))zbLoad();});
setInterval(()=>{if(api&&$('page-zandaobot').classList.contains('shown'))zbLoad();},300000);
