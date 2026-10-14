// GuildStats data is rendered as escaped text; remote HTML/scripts never enter the page.
const GS = {name:'', tab:'experience', follow:true, page:1, serial:0, hoverSerial:0, compareNames:['','','','',''], compareSeeded:false};
const GS_TABS = {experience:'Experiência', character:'Personagem', deaths:'Mortes', timeonline:'Tempo online', highscore:'Rankings', drome:'Drome', insomnia:'Insônia', history:'Histórico', compare:'Comparar personagens'};
const gsNumber = v => v == null ? 'Sem registro' : (v > 0 ? '+' : '') + Number(v).toLocaleString('pt-BR');
const gsDate = offset => { const d = new Date(); d.setDate(d.getDate()-offset); return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-'); };
const gsTranslate = value => ({Level:'Level', Online:'Estado online', Deaths:'Mortes', 'Character traded':'Negociações de personagem', 'Name changes':'Mudanças de nome', 'World transfers':'Transferências de mundo', 'Insomnia entries':'Registros de insônia', 'Exp in 30 days':'XP em 30 dias', 'Levels in 30 days':'Levels em 30 dias', 'Experience record':'Recorde de XP', Skills:'Skills', Attack:'Ataque', Fishing:'Fishing', Loyalty:'Loyalty', 'Charm points':'Pontos de charm', 'Boss points':'Pontos de boss', 'Drome score':'Pontuação do Drome', 'Bounty points':'Pontos de bounty', 'Weekly tasks':'Tarefas semanais', 'Phosphorus Record':'Recorde de Phosphorus', 'Max Drome':'Drome máximo', 'Ranking points':'Pontos de ranking', When:'Data' ,'Exp change':'XP líquida','Voc. rank':'Ranking da vocação',Lvl:'Level',Experience:'Experiência','Time online':'Tempo online','Avg exp/h':'XP/h média','Killed by':'Morto por','Exp lost':'XP perdida','Last month':'Mês anterior','Current month':'Mês atual','Current week':'Semana atual',Skill:'Skill',Value:'Valor',Position:'Posição',Rotation:'Rotação','Drome Level':'Level do Drome','Character Level':'Level do personagem',Efficiency:'Eficiência',Change:'Variação',Rank:'Ranking',Mon:'Seg',Tue:'Ter',Wed:'Qua',Thu:'Qui',Fri:'Sex',Sat:'Sáb',Sun:'Dom',Guild:'Guilda',Nationality:'Nacionalidade',Sex:'Sexo',Vocation:'Vocação','Achievements points':'Achievements',Titles:'Títulos','Account created':'Conta criada',World:'Mundo',Residence:'Residência','Last login':'Último login','Account status':'Conta','Tibian age':'Idade tibiana'}[value] || value);
function gsSignedText(value) {
  return esc(String(value)).replace(/(^|[\s(])([+−-]\d[\d.,]*%?)/g, (all, before, number) => {
    if (!/[1-9]/.test(number)) return all;
    return `${before}<span style="color:var(${number[0] === '+' ? '--good' : '--bad'})">${number}</span>`;
  });
}
function gsTable(headers, rows, comparison=false) {
  const body = rows.map(row => {
    if(comparison && row.length === 1) return `<tr class="gs-section"><td colspan="${headers.length}">${esc(gsTranslate(row[0]))}</td></tr>`;
    return `<tr>${row.map((cell, index)=>`<td>${comparison && index===0 ? esc(gsTranslate(cell)) : gsSignedText(cell)}</td>`).join('')}</tr>`;
  }).join('');
  return `<div class="gs-scroll"><table class="gs-table ${comparison?'gs-compare-table':''}"><thead><tr>${headers.map((h,index)=>`<th>${esc(comparison && index>0 ? h : gsTranslate(h))}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table></div>`;
}
function gsTiles(items) { return `<div class="gs-tiles">${items.map(([label,value])=>`<div class="card calmo"><div class="dica">${esc(label)}</div><b>${gsSignedText(value)}</b></div>`).join('')}</div>`; }
function gsRender(r) {
  if(r.erro) { $('gs-result').innerHTML=`<div class="card">${esc(r.erro)}</div>`; return; }
  let body=`<div class="card calmo"><h2 class="sub">${esc(r.name)} · ${GS_TABS[r.tab]}</h2><p class="dica">Atualização na fonte: ${esc(r.updated || 'não informada')} · Consulta: ${esc(r.fetched)}${r.stale?' · Cache anterior (falha ao atualizar)':''}</p><p class="dica">${esc(r.notice||'')}</p></div>`;
  if(r.erro_cache) body+=`<div class="card" role="status">${esc(r.erro_cache)}</div>`;
  if(r.tab==='experience') {
    const days=r.days||[];
    const exact=n=>days.find(d=>d.date===gsDate(n));
    body+=gsTiles([['Ontem · '+gsDate(1),gsNumber(exact(1)?.gain)],['Anteontem · '+gsDate(2),gsNumber(exact(2)?.gain)],['Último registro · '+(days[0]?.date||'—'),gsNumber(days[0]?.gain)]]);
    if(days.length) {
      const series=days.slice(0,31).reverse(), max=Math.max(1,...series.map(d=>Math.abs(d.gain||0)));
      body+=`<div class="card calmo"><h2 class="sub">XP diária · últimas datas disponíveis</h2><div class="gs-bars">${series.map(d=>`<div title="${esc(d.date+' · '+gsNumber(d.gain))}" style="height:${Math.max(2,Math.abs(d.gain||0)/max*100)}px;${d.gain<0?'background:#ff6464':''}"></div>`).join('')}</div><div class="dica">${esc(series[0].date)} → ${esc(series[series.length-1].date)} · Vermelho: perda líquida</div></div>`;
      body+=`<div class="card calmo" style="margin-top:12px"><h2 class="sub">XP mensal · período disponível</h2>${gsTable(['Mês','XP líquida','Datas disponíveis','Datas sem XP'],Object.entries(r.months||{}).sort().reverse().map(([m,v])=>[m,gsNumber(v.gain),v.days,v.missing]))}</div>`;
    }
  }
  if(r.summary) body+=gsTiles(['Mortes registradas','XP perdida (estimada)','Level estimado sem mortes','Mortes por jogadores'].map((l,i)=>[l,r.summary[i]]));
  if(r.profile) body+=`<div class="card calmo">${gsTable(['Informação','Valor'],Object.entries(r.profile).map(([k,v])=>[gsTranslate(k),v]))}</div>`;
  (r.tables||[]).forEach(t=>{ if(t.rows.length) body+=`<div class="card calmo" style="margin-top:12px">${gsTable(t.headers.length?t.headers:t.rows[0].map((_,i)=>'Coluna '+(i+1)),t.rows,r.tab==='compare')}</div>`; });
  if(r.tab==='deaths' && r.pages>1) body+=`<div class="acoes" style="margin-top:12px"><button class="btn" id="gs-prev" ${r.page<=1?'disabled':''}>← Anterior</button><span>Página ${r.page} de ${r.pages}</span><button class="btn" id="gs-next" ${r.page>=r.pages?'disabled':''}>Próxima →</button></div>`;
  $('gs-result').innerHTML=body;
  if($('gs-prev')) $('gs-prev').onclick=()=>{GS.page--;gsLoad();};
  if($('gs-next')) $('gs-next').onclick=()=>{GS.page++;gsLoad();};
}
async function gsLoad(force=false) {
  if(!api) return;
  const name=GS.follow?MEUS.atual:GS.name;
  GS.name=name||'';
  $('gs-follow').textContent=GS.follow?'Acompanhando o personagem em uso: '+(name||'nenhum'):'Consulta independente: '+name;
  $('gs-search').value=name||'';
  $('gs-tabs').innerHTML=Object.entries(GS_TABS).map(([k,v])=>`<button class="btn btn-sm ${GS.tab===k?'btn-primary':''}" data-gs-tab="${k}">${v}</button>`).join('');
  $('gs-tabs').querySelectorAll('[data-gs-tab]').forEach(b=>b.onclick=()=>{GS.tab=b.dataset.gsTab;GS.page=1;gsLoad();});
  const comparison = GS.tab==='compare';
  $('gs-search').hidden=comparison;
  $('gs-find').textContent=comparison?'Comparar':'Buscar';
  $('gs-compare-fields').hidden=!comparison;
  const serial=++GS.serial;
  if(comparison) {
    if(!GS.compareSeeded) { GS.compareNames[0]=name||''; GS.compareSeeded=true; }
    $('gs-follow').textContent='Compare de 2 a 5 personagens. Os campos 3, 4 e 5 são opcionais.';
    $('gs-compare-fields').innerHTML=GS.compareNames.map((value,index)=>`<div><label class="campo-label" for="gs-compare-${index}">Personagem ${index+1}${index>1?' · opcional':''}</label><input type="text" id="gs-compare-${index}" data-gs-compare="${index}" maxlength="60" value="${esc(value)}" placeholder="Nome do personagem"></div>`).join('');
    $('gs-compare-fields').querySelectorAll('[data-gs-compare]').forEach(input=>{
      input.oninput=()=>{GS.compareNames[Number(input.dataset.gsCompare)]=input.value;};
      input.onkeydown=event=>{if(event.key==='Enter') $('gs-find').click();};
    });
    const names=GS.compareNames.map(value=>value.trim()).filter(Boolean);
    if(names.length<2) { $('gs-result').innerHTML='<div class="card dica">Preencha pelo menos dois nomes e clique em Comparar.</div>'; return; }
    $('gs-result').innerHTML='<div class="card dica">Consultando a comparação do GuildStats… Se aparecer a verificação, conclua na janela do aplicativo.</div>';
    try { const result=await api.guildstats_comparar(names,force,true); if(serial===GS.serial) gsRender(result); }
    catch(error) { if(serial===GS.serial) $('gs-result').innerHTML='<div class="card">Falha na comparação. Tente atualizar novamente.</div>'; }
    return;
  }
  if(!name) {$('gs-result').innerHTML='<div class="card">Escolha um personagem nas configurações ou busque um nome acima.</div>';return;}
  $('gs-result').innerHTML='<div class="card dica">Consultando GuildStats… Se aparecer a verificação, conclua na janela do aplicativo.</div>';
  try { const r=await api.guildstats_buscar(name,GS.tab,force,GS.page,true); if(serial===GS.serial) gsRender(r); }
  catch(e) { if(serial===GS.serial) $('gs-result').innerHTML='<div class="card">Falha na consulta. Tente atualizar novamente.</div>'; }
}
async function gsHover(force=false) {
  const name=MEUS.atual, serial=++GS.hoverSerial;
  if(!name) {$('gs-hover').textContent='Selecione um personagem nas configurações.';return;}
  $('gs-hover').textContent=name+' · Consultando XP…';
  try {
    const r=await api.guildstats_buscar(name,'experience',force);
    if(serial!==GS.hoverSerial) return;
    if(r.erro) {$('gs-hover').textContent=name+' · '+r.erro;return;}
    const days=r.days||[], line=n=>{const day=gsDate(n), d=days.find(x=>x.date===day); return `${n===1?'Ontem':'Anteontem'} (${day}): ${gsNumber(d?.gain)}`;};
    $('gs-hover').innerHTML=`<b>${esc(name)}</b><br>${gsSignedText(line(1))}<br>${gsSignedText(line(2))}<br><span class="dica">Último registro: ${esc(days[0]?.date||'nenhum')}<br>Atualização: ${esc(r.updated||'não informada')}${r.stale?' · cache anterior':''}</span>`;
  } catch(e) {if(serial===GS.hoverSerial) $('gs-hover').textContent=name+' · Falha ao consultar GuildStats.';}
}
$('gs-find').onclick=()=>{if(GS.tab==='compare') {gsLoad(true);return;}const name=$('gs-search').value.trim();if(!name)return;GS.follow=false;GS.name=name;GS.page=1;gsLoad();};
$('gs-search').onkeydown=e=>{if(e.key==='Enter') $('gs-find').click();};
$('gs-active').onclick=()=>{if(GS.tab==='compare') {GS.compareNames[0]=MEUS.atual||'';GS.compareSeeded=true;}GS.follow=true;GS.page=1;gsLoad();};
$('gs-refresh').onclick=async()=>{await gsLoad(true);gsHover();};
$('gs-site').onclick=()=>{gsLoad(true);};
$('gs-menu').addEventListener('mouseenter',()=>gsHover());
$('gs-menu').addEventListener('focus',()=>gsHover());
PERS_OUVINTES.push(()=>{GS.follow=true;GS.page=1;GS.name=MEUS.atual;GS.serial++;gsHover();if($('page-guildstats').classList.contains('shown'))gsLoad();else $('gs-result').innerHTML='';});
