// Consultas que a Mensagem do dia pode incluir: [chave, rótulo, tipo do campo]. Campo vazio = padrão do personagem em uso.
const WB_TICKS=[['mini','World Board manual (preencher)',''],['kill','Top 10 criaturas mortas ontem','mundo'],['exp_mundo','Top 10 XP do servidor (ontem)','mundo'],['exp_guild','Top XP da guild (ontem)','guild'],['guild','Resumo da guild','guild'],['online_guild','Online da guild','guild'],['char','Personagem (ficha e mortes recentes)','personagem'],['transfer','Transferências de mundo (10 dias)','mundo']];
const WB_CHAVE='zt-mensagem-dia-ticks';
const WB={draft:'',dirty:false,full:false,fields:{},msg:'',status:'',unknown:[],ticks:{mini:true},args:{}};
try{const s=JSON.parse(localStorage.getItem(WB_CHAVE)||'null');if(s&&typeof s==='object'){WB.ticks={...WB.ticks,...s.ticks};WB.args={...s.args};}}catch(e){/* sem armazenamento: vale o padrão */}
const wbGuardar=()=>{try{localStorage.setItem(WB_CHAVE,JSON.stringify({ticks:WB.ticks,args:WB.args}));}catch(e){/* ignora */}};
function wbPadrao(r,tipo){return 'Padrão: '+(tipo==='mundo'?(r.mundo||'mundo do personagem'):tipo==='guild'?'guild de '+(r.personagem||'personagem em uso'):(r.personagem||'personagem em uso'));}
function wbPanel(r){
 const b=r.world_board;
 const board=`<details class="wb-board" data-zb-key="board" ${zbOpen('board',!!WB.draft)}><summary>World Board manual <span>${b?(b.valido?'🟢 registro de hoje':'🕒 registro anterior'):'colar Server Log'}</span></summary><p>Perfil: <b>${esc(r.personagem||'nenhum')}</b> · Mundo: <b>${esc(r.mundo||'selecione um mundo')}</b>. Use a placa na Adventurers’ Guild e cole o Server Log. Ao gerar a mensagem, o texto colado é salvo neste computador e entra nela.</p>${b?`<p>${b.valido?'🟢 Registro de hoje':'🕒 Registro anterior'} · ${esc(zbDate(b.dia))} · ${b.eventos.length} mudanças · ${b.completo?'completo':'parcial'}</p><ul>${b.eventos.map(e=>`<li>${esc(e.rotulo||e.nome)} · ${esc(e.local)} ${esc(e.detalhe||'')}</li>`).join('')}</ul><button id="wb-remove">Remover registro</button>`:''}<textarea id="wb-text" rows="6" placeholder="Cole aqui as mensagens da placa…">${esc(WB.draft)}</textarea><div class="wb-actions"><label>Dia do Tibia <input id="wb-date" type="date" value="${esc(r.dia)}" max="${esc(r.dia)}"></label><label><input id="wb-full" type="checkbox" ${WB.full?'checked':''}> Copiei todas as mensagens da placa</label></div><p class="zb-muted">Yasir ausente só será confirmado com um trecho completo, sem mensagens desconhecidas. A placa não informa o boss Dream Court.</p>${WB.unknown.length?`<p class="zb-warning-text">${WB.unknown.length} linhas não reconhecidas: ausência não confirmada.</p><pre>${esc(WB.unknown.join('\n'))}</pre>`:''}</details>`;
 const ticks=WB_TICKS.map(([k,label,tipo])=>`<div class="wb-tick"><label><input type="checkbox" data-wb-tick="${k}" ${WB.ticks[k]?'checked':''}> ${label}</label>${tipo?`<input data-wb-arg="${k}" maxlength="40" value="${esc(WB.args[k]||'')}" placeholder="${esc(wbPadrao(r,tipo))}" aria-label="${esc(label)}: outro ${tipo} (opcional)">`:''}</div>`).join('');
 return `<details class="zb-panel wb-panel" data-zb-key="mensagem" ${zbOpen('mensagem',false)}><summary>Mensagem do dia</summary><p>Complete os dados manuais que desejar. Campos vazios aparecem como ❓. Revise a mensagem antes de copiar.</p><div class="wb-fields">${[['comunidade','Comunidade'],['assinatura','Assinatura'],['deeplings','Boss Deeplings'],['regiao','Região boostada'],['roshamuul','Roshamuul / robôs'],['drome','Tibia Drome (fim da rotação)'],['coin_compra','TC: comprar (gp)'],['coin_venda','TC: vender (gp)'],['coin_hora','Horário dos preços']].map(([k,label])=>`<label>${label}<input data-wb-field="${k}" maxlength="200" value="${esc(WB.fields[k]??(k==='assinatura'?r.personagem||'':''))}"></label>`).join('')}</div><fieldset class="wb-ticks"><legend>Incluir na mensagem</legend><p class="zb-muted">Campo vazio usa o personagem em uso. Digite outro mundo, guild ou nome se quiser.</p>${ticks}</fieldset>${board}<button id="wb-generate">Gerar mensagem do dia</button><textarea id="wb-message" rows="15" placeholder="Sua mensagem aparecerá aqui e poderá ser editada.">${esc(WB.msg)}</textarea><button id="wb-copy">Copiar mensagem</button><p id="wb-report-status" aria-live="polite">${esc(WB.status)}</p></details>`;
}
function wbBind(r){
 document.querySelectorAll('[data-wb-field]').forEach(i=>i.oninput=()=>{WB.fields[i.dataset.wbField]=i.value;WB.dirty=true;});
 document.querySelectorAll('[data-wb-tick]').forEach(i=>i.onchange=()=>{WB.ticks[i.dataset.wbTick]=i.checked;wbGuardar();});
 document.querySelectorAll('[data-wb-arg]').forEach(i=>i.oninput=()=>{WB.args[i.dataset.wbArg]=i.value.trim();WB.dirty=true;wbGuardar();});
 const t=$('wb-text');
 t.oninput=()=>{WB.draft=t.value;WB.dirty=!!t.value;};
 $('wb-full').onchange=()=>{WB.full=$('wb-full').checked;};
 $('wb-message').oninput=()=>{WB.msg=$('wb-message').value;WB.dirty=true;};
 const error=x=>toast(x,true);
 if($('wb-remove'))$('wb-remove').onclick=async()=>{try{const x=await api.world_board_remover(r.mundo,r.world_board.dia,r.personagem);if(x.erro)return error(x.erro);zbLoad();}catch(e){error('Falha ao remover registro.');}};
 $('wb-generate').onclick=async()=>{
  const btn=$('wb-generate'),status=$('wb-report-status');
  btn.disabled=true;status.textContent='Gerando a mensagem…';
  try{
   let salvo='';
   if(t.value.trim()){
    // o World Board colado é salvo no perfil antes, para a mensagem já sair com ele
    const a=await api.world_board_analisar(t.value,r.mundo,$('wb-date').value,$('wb-full').checked);
    if(a.erro){status.textContent='';return error(a.erro);}
    const s=await api.world_board_salvar(t.value,r.mundo,$('wb-date').value,$('wb-full').checked,a.personagem);
    if(s.erro){status.textContent='';return error(s.erro);}
    WB.draft='';WB.full=false;WB.unknown=a.nao_reconhecidas||[];
    salvo=`World Board salvo: ${a.eventos.length} mudanças. `;
   }
   const extras=WB_TICKS.filter(([k])=>k!=='mini'&&WB.ticks[k]).map(([k])=>({chave:k,arg:WB.args[k]||''}));
   const x=await api.zandaobot_mensagem(r.mundo,WB.fields,extras,!!WB.ticks.mini);
   if(x.erro){status.textContent='';return error(x.erro);}
   WB.msg=x.mensagem;WB.dirty=false;WB.status=salvo+'Mensagem gerada. Revise os dados manuais e a data antes de compartilhar.';
   if(salvo)return zbLoad();  // redesenha os cards (Yasir) com o registro novo; a mensagem fica guardada em WB
   $('wb-message').value=WB.msg;status.textContent=WB.status;
  }catch(e){status.textContent='';error('Falha ao gerar mensagem.');}
  finally{if(btn.isConnected)btn.disabled=false;}
 };
 $('wb-copy').onclick=async()=>{const msg=$('wb-message').value;if(!msg)return error('Gere a mensagem primeiro.');try{await navigator.clipboard.writeText(msg);toast('Mensagem copiada.');}catch(e){$('wb-message').focus();$('wb-message').select();$('wb-report-status').textContent='Texto selecionado. Pressione Ctrl+C para copiar.';}};
}
