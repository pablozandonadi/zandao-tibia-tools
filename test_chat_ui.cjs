const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

class Element {
  constructor(tag = 'div') { this.tagName = tag; this.children = []; this.listeners = {}; this.className = ''; this.textContent = ''; this.value = ''; this.disabled = false; this.scrollTop = 0; this.scrollHeight = 500; this.focused = 0; }
  set innerHTML(value) { throw new Error('O chat nunca usa HTML'); }
  setAttribute(name,value) { this[name]=value; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  querySelector(selector) { return selector === 'button[type=submit]' ? this.submit : undefined; }
  focus() { this.focused++; }
}
const elements = Object.fromEntries(['chat-mensagens', 'chat-form', 'chat-texto', 'chat-limpar', 'chat-digitando', 'chat-canal-local', 'chat-canal-log', 'chat-canal-help', 'chat-canal-ia', 'chat-canal-ajuda', 'assistente-instrucoes'].map(id => [id, new Element()]));
elements['chat-form'].submit = new Element('button');
global.document = {getElementById: id => elements[id], createElement: tag => new Element(tag)};
global.window = {addEventListener() {}};
global.PERS_OUVINTES = [];
global.MEUS = {atual:'Teste',lista:[{nome:'Teste',mundo:'Antica'},{nome:'Outro',mundo:'Secura'}]};
const ui = require('./web/chat.js');

const calls = [];
let answer;
const mundoCalls = [];
let mundoFalha = false;
window.pywebview = {api: {
  assistente_chat(texto,modo) { calls.push(modo ? ['chat',texto,modo] : ['chat', texto]); return new Promise((resolve, reject) => { answer = {resolve, reject}; }); },
  async assistente_chat_limpar() { calls.push(['limpar']); return {ok: true}; },
  zandaobot_buscar(mundo) {
    mundoCalls.push(mundo);
    if (mundoFalha) return Promise.reject(new Error('sem rede'));
    return Promise.resolve({rashid: 'Ankrahmun', server_save_ms: Date.now() + (5 * 60 + 20) * 60000 + 30000, mundo: 'Antica',
      boostados: {boss: {nome: 'Drume'}, criatura: {nome: 'Demon'}}, dream_court: {nome: 'Plagueroot'}, yasir: {estado: 'ausente'},
      servidor: {name: 'Antica', players_online: 412}, avisos_mundo: [{texto: 'Manutenção hoje.'}]});
  }
}};
const flush = () => new Promise(resolve => setImmediate(resolve));
const caixa = elements['chat-mensagens'], form = elements['chat-form'], campo = elements['chat-texto'], enviar = form.submit;
const tag = (balao, nome) => balao.children.find(child => child.tagName === nome);
const submit = () => { let prevented = false; form.listeners.submit({preventDefault() { prevented = true; }}); return prevented; };

(async () => {
  // Balões: tudo entra por textContent, o "Entendi" só aparece quando houve ação.
  const html = '<img src=x onerror=alert(1)>';
  const bot = ui.render('chat-bot', html, '—');
  assert.equal(bot.className, 'chat-bot');
  assert.equal(tag(bot, 'p').textContent, html, 'HTML não é interpretado');
  assert.equal(tag(bot, 'small'), undefined, 'Sem ação, sem "Entendi"');
  assert.equal(tag(ui.render('chat-bot', 'ok', ''), 'small'), undefined);
  assert.equal(tag(ui.render('chat-bot', 'ok'), 'small'), undefined);
  const entendi = ui.render('chat-bot', 'Drume: 1 abate.', 'Registrar abate · <b>Drume</b>');
  assert.equal(tag(entendi, 'small').textContent, 'Entendi: Registrar abate · <b>Drume</b>');
  assert.equal(caixa.children.at(-1), entendi);
  assert.equal(caixa.scrollTop, caixa.scrollHeight, 'Rola para a última mensagem');
  caixa.replaceChildren();

  // Enter/botão: um envio por vez, botão desabilitado enquanto espera.
  ui.boot();
  assert.equal(submit(), true, 'O formulário nunca recarrega a página');
  campo.value = '   ';
  submit();
  assert.deepEqual(calls, [], 'Texto vazio não vai ao app');
  campo.value = '  matei o Drume ';
  submit();
  assert.deepEqual(calls, [['chat', 'matei o Drume']]);
  assert.equal(enviar.disabled, true, 'Botão desabilitado enquanto espera');
  assert.equal(elements['chat-digitando'].hidden,false);
  assert.equal(campo.value, '', 'Campo limpo após enviar');
  assert.deepEqual(caixa.children.map(child => child.className), ['chat-eu']);
  assert.equal(tag(caixa.children[0], 'p').textContent, 'matei o Drume');
  campo.value = 'outra pergunta';
  submit();
  assert.equal(calls.length, 1, 'Segundo envio durante a espera é ignorado');
  answer.resolve({resposta: 'Drume: 1 abates reais.', entendi: 'Registrar abate · Drume', origem: 'local'});
  await flush();
  assert.deepEqual(caixa.children.map(child => child.className), ['chat-eu', 'chat-bot']);
  assert.equal(tag(caixa.children[1], 'p').textContent, 'Drume: 1 abates reais.');
  assert.equal(tag(caixa.children[1], 'small').textContent, 'Entendi: Registrar abate · Drume');
  assert.equal(enviar.disabled, false);
  assert.equal(elements['chat-digitando'].hidden,true);
  assert.equal(campo.value, 'outra pergunta', 'O que foi digitado durante a espera é mantido');

  // Erros: do app ({erro}) e da própria ponte (promessa rejeitada).
  submit();
  answer.resolve({erro: 'Não consegui responder agora.'});
  await flush();
  const erro = caixa.children.at(-1);
  assert.ok(erro.className.split(' ').includes('chat-bot') && erro.className.split(' ').includes('chat-erro'));
  assert.equal(tag(erro, 'p').textContent, 'Não consegui responder agora.');
  assert.equal(enviar.disabled, false);
  campo.value = 'de novo';
  submit();
  answer.reject(new Error('A ponte caiu'));
  await flush();
  assert.equal(tag(caixa.children.at(-1), 'p').textContent, 'A ponte caiu');
  assert.equal(enviar.disabled, false, 'Erro também libera o botão');

  // Limpar zera a tela e o histórico do app.
  await elements['chat-limpar'].listeners.click();
  assert.deepEqual(calls.at(-1), ['limpar']);
  assert.equal(caixa.children.length, 0);

  // Trocar perfil limpa imediatamente e ignora uma resposta atrasada do perfil antigo.
  campo.value='pergunta pendente';submit();
  MEUS.atual='Outro';PERS_OUVINTES[0]();
  assert.equal(caixa.children.length,0);
  const clears=calls.filter(call=>call[0]==='limpar').length;
  PERS_OUVINTES[0]();
  assert.equal(calls.filter(call=>call[0]==='limpar').length,clears,'Mesmo perfil não limpa duas vezes');
  answer.resolve({resposta:'resposta antiga',entendi:'—'});await flush();
  assert.equal(caixa.children.length,0);

  elements['chat-canal-ia'].listeners.keydown({key:'Home',preventDefault(){}});
  assert.equal(elements['chat-canal-local']['aria-selected'],'true');
  assert.equal(elements['chat-canal-local'].focused,1);
  elements['chat-canal-local'].listeners.keydown({key:'End',preventDefault(){}});
  assert.equal(elements['chat-canal-ia']['tabindex'],'0');

  // Canais independentes: Local Chat sinaliza modo local; log é somente leitura.
  ui.selecionar('local');
  campo.value='timer 30s';submit();
  assert.deepEqual(calls.at(-1),['chat','timer 30s','local']);
  answer.resolve({resposta:'Timer criado.',entendi:'Criar timer'});await flush();
  ui.selecionar('ia');
  assert.equal(caixa.children.length,0,'A conversa local não aparece no Tudo IA');
  window.chatEstado({context:{character_id:'Outro',world_id:'Secura'},log:[{id:'real',texto:'Registrar abate · Drume'}]});
  window.chatAvisos([{id:'alerta',texto:'Timer terminou.'}]);
  ui.selecionar('log');
  assert.equal(form.hidden,true);
  assert.equal(caixa.children.length,1,'Alerta já está no histórico: não duplica no Server Log');
  assert.equal(tag(caixa.children[0],'p').textContent,'Registrar abate · Drume');
  const previousCalls=calls.length;
  await ui.enviar('não enviar');
  assert.equal(calls.length,previousCalls,'Server Log nunca envia mensagens');
  ui.selecionar('ia');
  assert.equal(form.hidden,false);

  // Help: instruções somente leitura (sem formulário, sem envio, sem limpar).
  const instrucoes = elements['assistente-instrucoes'];
  ui.selecionar('help');
  assert.equal(instrucoes.hidden, false);
  assert.equal(caixa.hidden, true);
  assert.equal(form.hidden, true);
  assert.equal(elements['chat-canal-help']['aria-selected'], 'true');
  assert.equal(elements['chat-canal-help']['aria-controls'], 'assistente-instrucoes');
  assert.equal(elements['chat-canal-ia']['aria-selected'], 'false');
  const antesHelp = calls.length;
  campo.value = 'x'; submit(); await ui.enviar('x'); await ui.limpar();
  assert.equal(calls.length, antesHelp, 'Help nunca envia nem limpa a conversa');
  elements['chat-canal-help'].listeners.keydown({key: 'ArrowRight', preventDefault() {}});
  assert.equal(elements['chat-canal-ia']['aria-selected'], 'true', 'Help vem antes do Tudo IA');
  assert.equal(instrucoes.hidden, true);
  assert.equal(caixa.hidden, false);
  assert.equal(form.hidden, false);
  elements['chat-canal-ia'].listeners.keydown({key: 'ArrowLeft', preventDefault() {}});
  assert.equal(elements['chat-canal-help']['aria-selected'], 'true', 'Ordem: Local Chat, Server Log, Help, Tudo IA');
  ui.selecionar('ia');
  campo.value = '';

  // Local Chat: informações do mundo (as da Home) no topo, antes da conversa; consulta no máximo 1x por minuto.
  mundoFalha = true;
  MEUS.atual = 'Teste'; PERS_OUVINTES[0]();
  ui.selecionar('local'); await flush();
  assert.deepEqual(caixa.children.map(child => tag(child, 'p').textContent), ['Informações do mundo indisponíveis agora.'], 'Sem rede: avisa, não quebra');
  mundoFalha = false;
  MEUS.atual = 'Outro'; PERS_OUVINTES[0]();
  ui.selecionar('local'); await flush();
  const textos = caixa.children.map(child => tag(child, 'p').textContent);
  assert.ok(caixa.children.slice(0, 8).every(child => child.className === 'chat-registro chat-mundo'));
  assert.equal(textos[0], 'Rashid hoje: Ankrahmun');
  assert.match(textos[1], /^Server save em 5h20 \(às \d\d:\d\d, horário do seu PC\)$/);
  assert.deepEqual(textos.slice(2, 7), ['Boss do dia: Drume', 'Criatura do dia: Demon', 'Dream Court em Antica: Plagueroot', 'Yasir: ausente', 'Antica: 412 jogadores online']);
  assert.equal(textos[7], 'Aviso: Manutenção hoje.');
  campo.value = 'timer 30s'; submit();
  assert.deepEqual(calls.at(-1), ['chat', 'timer 30s', 'local'], 'Local Chat continua mandando só comandos locais');
  answer.resolve({resposta: 'Timer criado.', entendi: 'Criar timer'}); await flush();
  assert.deepEqual(caixa.children.slice(-2).map(child => child.className), ['chat-eu', 'chat-bot'], 'A conversa vem depois das informações do mundo');
  assert.equal(caixa.children.length, 10);
  const consultas = mundoCalls.length;
  assert.equal(mundoCalls.at(-1), '', 'Mundo do personagem em uso, como na Home');
  window.chatEstado({context: {character_id: 'Outro', world_id: 'Secura'}, log: []}); await flush();
  assert.equal(mundoCalls.length, consultas, 'Menos de 1 minuto: não consulta de novo');
  const agora = Date.now;
  Date.now = () => agora() + 61000;
  window.chatEstado({context: {character_id: 'Outro', world_id: 'Secura'}, log: []}); await flush();
  assert.equal(mundoCalls.length, consultas + 1, 'Passado 1 minuto, com o Local Chat aberto, atualiza');
  ui.selecionar('ia');
  Date.now = () => agora() + 200000;
  window.chatEstado({context: {character_id: 'Outro', world_id: 'Secura'}, log: []}); await flush();
  Date.now = agora;
  assert.equal(mundoCalls.length, consultas + 1, 'Fora do Local Chat não consulta');
  assert.equal(caixa.children.length, 0, 'As informações do mundo não aparecem no Tudo IA');

  // Tela: aba Chat só com o chat, voz escondida mas presente, chat.js depois do assistente.js.
  const index = fs.readFileSync(path.join(__dirname, 'web/index.html'), 'utf8');
  const at = text => { const i = index.indexOf(text); assert.ok(i >= 0, text); return i; };
  assert.equal((index.match(/id="chat-form"/g) || []).length, 1);
  assert.equal(index.includes('id="assistente-monitor-abrir"'),false);
  assert.ok(index.includes('data-assistente-tab="character-track"'));
  assert.ok(index.includes('src="assistente_canais.js"'));
  assert.ok(index.includes('class="assistente-nav"'));
  assert.ok(at('id="chat-mensagens" role="log" aria-live="polite"') < at('id="chat-form"'));
  assert.ok(at('src="assistente.js"') < at('src="chat.js"'));
  const painel = nome => { const i = at(`data-assistente-panel="${nome}"`), proximo = index.indexOf('data-assistente-panel="', i + 10); return index.slice(i, proximo); };
  const chat = painel('overview'), timers = painel('timers'), shared = painel('shared'), upo = painel('upo');
  const paraTimers = ['timer-editor', 'timer-label', 'timer-duration', 'timer-unit', 'timer-save', 'timer-history', 'assistente-timers-list', 'voz-feedback', 'voz-avisos', 'assistente-overview', 'voz-pausado'];
  for (const id of paraTimers) { assert.ok(timers.includes(`id="${id}"`), `${id} agora fica em Timers Gerais`); assert.ok(!chat.includes(`id="${id}"`), `${id} saiu da aba Chat`); }
  for (const id of ['chat-canal-local', 'chat-canal-log', 'chat-canal-help', 'chat-canal-ia', 'chat-mensagens', 'chat-digitando', 'chat-form', 'chat-texto', 'chat-limpar', 'assistente-instrucoes']) assert.ok(chat.includes(`id="${id}"`), `${id} fica na aba Chat`);
  assert.ok(at('id="chat-canal-local"') < at('id="chat-canal-log"') && at('id="chat-canal-log"') < at('id="chat-canal-help"') && at('id="chat-canal-help"') < at('id="chat-canal-ia"'), 'Local Chat | Server Log | Help | Tudo IA');
  assert.ok(chat.includes('>Help</button>'));
  assert.ok(at('id="chat-mensagens"') < at('id="assistente-instrucoes"') && at('id="assistente-instrucoes"') < at('id="chat-form"'), 'Instruções dentro do cartão do chat');
  assert.ok(!index.includes('data-assistente-tab="instrucoes"') && !index.includes('data-assistente-panel="instrucoes"'), 'Sem a aba Instruções');
  assert.ok(!index.includes('aba Instruções'));
  assert.ok(chat.split('<q>').length > 40, 'As frases de exemplo continuam no Help');
  const pausado = at('<div id="voz-pausado" hidden>');
  for (const id of ['voz-status', 'voz-microfone', 'voz-esfera', 'voz-ajuda', 'voz-ajuda-texto', 'voz-ajuda-area', 'voz-ouvi', 'voz-entendi', 'voz-resposta']) assert.ok(at(`id="${id}"`) > pausado, `${id} fica escondido no #voz-pausado`);
  // Ferramentas foi embora: Shared XP numa aba só (calculadora ao vivo + formulários) e "Quando eu upo?" ganhou aba.
  assert.ok(!index.includes('data-pagina="ferr"') && !index.includes('id="page-ferr"') && !/irPara\('ferr'\)|abrirFerramentas|Abrir no Assistente Tibiano/.test(index));
  assert.equal((index.match(/data-assistente-panel="shared"/g) || []).length, 1);
  for(const id of ['shared-lookup','shared-party','shared-mode-reference','shared-mode-party','assistente-level-form'])assert.ok(shared.includes(`id="${id}"`));
  for(const id of ['voz-form','voz-lista','f-levels','f-shared-res'])assert.equal(index.includes(`id="${id}"`),false);
  assert.ok(index.includes('data-assistente-panel="upo"'));
  for (const id of ['f-up-sel', 'f-up-nome', 'f-up-info', 'f-up-alvo', 'f-up-xp', 'f-up-xph', 'f-up-calc', 'f-up-res']) assert.ok(upo.includes(`id="${id}"`), `${id} fica na aba Quando eu upo?`);
  for (const id of new Set([...index.matchAll(/\$\('(f-[a-z-]+)'\)/g)].map(m => m[1]).filter(id=>!['f-levels','f-shared-res'].includes(id)))) assert.equal((index.match(new RegExp(`id="${id}"`, 'g')) || []).length, 1, `${id} existe uma vez`);
  console.log('chat UI: safe bubbles, single send, errors, clear, Help channel, Local Chat world info and page wiring passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
