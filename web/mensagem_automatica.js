// Preferências locais independentes da mensagem manual; não executam geração ou envio.
const MA_FIELDS=[['comunidade','Comunidade'],['assinatura','Assinatura'],['deeplings','Boss Deeplings'],['regiao','Região boostada'],['roshamuul','Roshamuul / robôs'],['drome','Tibia Drome (fim da rotação)'],['coin_compra','TC: comprar (gp)'],['coin_venda','TC: vender (gp)'],['coin_hora','Horário dos preços']];
const MA_BLOCKS=[['dia','Data'],['saudacao','Saudação'],['frase','Mensagem do dia'],['mundo','Mundo'],['calendario','Eventos do Tibia'],['yasir','Yasir (consulta online)'],['rashid','Rashid'],['criatura','Criatura boostada'],['boss','Boss boostado'],['dream','Dream Court'],['dream_mortes','Dream Court — mortes (Last Day)'],['mudancas_online','Outras world changes (consulta online)'],['server_save','Próximo SS']];
const MA_EXTRAS=[['kill','Top 10 criaturas mortas ontem','mundo'],['exp_mundo','Top 10 XP do servidor (ontem)','mundo'],['exp_guild','Top XP da guild (ontem)','guild'],['guild','Resumo da guild','guild'],['online_guild','Online da guild','guild'],['char','Personagem (ficha e mortes recentes)','personagem'],['transfer','Entraram e saíram do mundo (10 dias)','mundo']];
const MA_DRAFTS=new Map();
function maKey(r){return 'zt-mensagem-automatica-v1:'+JSON.stringify([r.personagem||'',r.mundo||''].map(v=>String(v).trim().toLowerCase()));}
function maRead(r){
 if(MA_DRAFTS.has(maKey(r)))return {value:MA_DRAFTS.get(maKey(r)),notice:''};
 try{const raw=localStorage.getItem(maKey(r));if(!raw)return {value:{},notice:''};const value=JSON.parse(raw);if(!value||typeof value!=='object'||Array.isArray(value))throw Error();return {value,notice:''};}
 catch(e){return {value:{},notice:'Não foi possível carregar suas preferências. Revise os campos antes de salvar.'};}
}
function maPanel(r){
 const {value:c,notice}=maRead(r),has=(group,key)=>c[group]?.[key]===true,text=(group,key)=>typeof c[group]?.[key]==='string'?c[group][key].slice(0,200):'';
 const tick=(group,key,label)=>`<label><input type="checkbox" data-ma-${group}="${key}" ${has(group,key)?'checked':''}> ${esc(label)}</label>`;
 const fields=MA_FIELDS.map(([k,label])=>`<div class="ma-field">${tick('fields',k,label)}<input data-ma-value="${k}" maxlength="200" value="${esc(text('values',k))}" aria-label="${esc(label)}: valor da configuração automática" placeholder="Valor opcional"></div>`).join('');
 const extras=MA_EXTRAS.map(([k,label,tipo])=>`<div class="wb-tick">${tick('extras',k,label)}<input data-ma-arg="${k}" maxlength="40" value="${esc(text('args',k).slice(0,40))}" placeholder="${esc('Padrão: '+(tipo==='mundo'?(r.mundo||'mundo do personagem'):tipo==='guild'?'guild de '+(r.personagem||'personagem em uso'):(r.personagem||'personagem em uso')))}" aria-label="${esc(label)}: outro ${tipo} (opcional)"></div>`).join('');
 const time=k=>typeof c[k]==='string'&&/^([01]\d|2[0-3]):[0-5]\d$/.test(c[k])?c[k]:'';
 const zone=typeof c.timezone==='string'?c.timezone.slice(0,100):'';
 return `<details class="wb-board ma-panel" data-zb-key="mensagem-automatica" ${typeof zbOpen==='function'?zbOpen('mensagem-automatica',false):''}><summary>Mensagem automática</summary><p><strong>Envio automático ainda não conectado</strong></p><p>Escolha o conteúdo e os horários para o envio automático futuro. Salvar não ativa a geração nem o envio. O World Board manual fica fora desta configuração.</p><p>Personagem: <b>${esc(r.personagem||'nenhum')}</b> · Mundo: <b>${esc(r.mundo||'nenhum')}</b></p><p class="zb-muted">Preferências salvas neste computador, por personagem e mundo.</p><fieldset class="wb-ticks"><legend>Conteúdo básico</legend>${MA_BLOCKS.map(([k,label])=>tick('blocks',k,label)).join('')}</fieldset><fieldset class="wb-ticks"><legend>Variáveis manuais da mensagem automática</legend><p class="zb-muted">Marque o que deseja incluir e preencha os valores próprios desta configuração. Eles não alteram a mensagem manual.</p><div class="wb-fields">${fields}</div><label>Data dos valores manuais<input type="date" data-ma-manual value="${typeof c.manualDate==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(c.manualDate)?c.manualDate:''}"></label><p class="zb-muted">Valores como preços e bosses manuais só serão válidos para o dia do Tibia informado.</p></fieldset><fieldset class="wb-ticks"><legend>Consultas adicionais</legend><p class="zb-muted">Campo vazio usa o contexto acima.</p>${extras}</fieldset><fieldset class="wb-ticks"><legend>Horários</legend><div class="wb-fields"><label>Gerar às<input type="time" data-ma-time="generateAt" value="${time('generateAt')}"></label><label>Enviar às<input type="time" data-ma-time="sendAt" value="${time('sendAt')}"></label><label>Fuso horário<input data-ma-zone maxlength="100" value="${esc(zone)}" placeholder="Ex.: America/Cuiaba"></label></div><p class="zb-muted">Envio igual ou posterior à geração. Horários vazios são permitidos para salvar um rascunho; nenhuma agenda está ativa.</p></fieldset><button type="button" data-ma-save>Salvar configuração</button> <button type="button" data-ma-preview>Gerar prévia</button> <button type="button" data-ma-export>Exportar configuração</button> <button type="button" data-ma-portal>Gerenciar conexão e agenda</button><pre data-ma-preview-result></pre><p data-ma-status role="status" aria-live="polite">${esc(notice)}</p></details>`;
}
function maBind(r){
 const panel=document.querySelector('.ma-panel');if(!panel)return;
 const collect=()=>{
  const c={blocks:{},fields:{},values:{},extras:{},args:{}};
  for(const group of ['blocks','fields','extras'])panel.querySelectorAll(`[data-ma-${group}]`).forEach(i=>{c[group][i.getAttribute('data-ma-'+group)]=i.checked;});
  for(const [attr,group] of [['value','values'],['arg','args']])panel.querySelectorAll(`[data-ma-${attr}]`).forEach(i=>{c[group][i.getAttribute('data-ma-'+attr)]=i.value.trim();});
  panel.querySelectorAll('[data-ma-time]').forEach(i=>{c[i.dataset.maTime]=i.value;});
  c.timezone=panel.querySelector('[data-ma-zone]').value.trim();
  c.manualDate=panel.querySelector('[data-ma-manual]').value;
  return c;
 };
 const payload=()=>({...collect(),personagem:r.personagem,mundo:r.mundo});
 panel.querySelector('[data-ma-preview]').onclick=async()=>{
  const status=panel.querySelector('[data-ma-status]'),button=panel.querySelector('[data-ma-preview]');button.disabled=true;
  try{if(typeof api?.mensagem_automatica_previa!=='function')throw Error();const result=await api.mensagem_automatica_previa(payload());if(result.erro){status.textContent=result.erro;return;}panel.querySelector('[data-ma-preview-result]').textContent=result.text;status.textContent='Prévia gerada para '+result.reference_date+'. Nenhuma mensagem foi enviada.';}
  catch(e){status.textContent='Não foi possível gerar a prévia. Nenhuma mensagem foi enviada.';}finally{button.disabled=false;}
 };
 panel.querySelector('[data-ma-export]').onclick=()=>{
  const blob=new Blob([JSON.stringify(payload(),null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='mensagem-automatica.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);panel.querySelector('[data-ma-status]').textContent='Configuração exportada. Você também pode abrir a gestão diretamente pelo aplicativo.';
 };
 panel.querySelector('[data-ma-portal]').onclick=async()=>{
  const status=panel.querySelector('[data-ma-status]');try{if(typeof api?.mensagem_automatica_abrir_portal!=='function')throw Error();const result=await api.mensagem_automatica_abrir_portal(payload());status.textContent=result.erro||'Gestão aberta no aplicativo com sua configuração.';}catch(e){status.textContent='O portal de conexão ainda não está disponível.';}
 };
 const remember=()=>MA_DRAFTS.set(maKey(r),collect());
 panel.addEventListener('input',remember);panel.addEventListener('change',remember);
 panel.querySelector('[data-ma-save]').onclick=()=>{
  const status=panel.querySelector('[data-ma-status]'),c=collect();
  MA_DRAFTS.set(maKey(r),c);
  if(!r.personagem||!r.mundo){status.textContent='Selecione um personagem e um mundo antes de salvar.';return;}
  if((c.generateAt&&!/^([01]\d|2[0-3]):[0-5]\d$/.test(c.generateAt))||(c.sendAt&&!/^([01]\d|2[0-3]):[0-5]\d$/.test(c.sendAt))){status.textContent='Informe horários válidos.';return;}
  if(c.generateAt&&c.sendAt&&c.sendAt<c.generateAt){status.textContent='O envio deve ser igual ou posterior à geração no mesmo dia local.';return;}
  if((c.generateAt||c.sendAt)&&!c.timezone){status.textContent='Informe o fuso horário.';return;}
  if(c.timezone){try{new Intl.DateTimeFormat('pt-BR',{timeZone:c.timezone});}catch(e){status.textContent='Fuso inválido. Use um fuso como America/Cuiaba.';return;}}
  try{localStorage.setItem(maKey(r),JSON.stringify(c));MA_DRAFTS.delete(maKey(r));status.textContent='Configuração salva neste computador. O envio automático ainda não está ativo.';}
  catch(e){status.textContent='Não foi possível salvar. Verifique o espaço disponível neste computador e tente novamente.';}
 };
}
