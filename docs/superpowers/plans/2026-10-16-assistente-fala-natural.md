# Assistente Tibiano — fala natural: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O jogador fala de forma natural e o assistente acerta a ação; na dúvida, pergunta por voz; lembra o assunto por ~1 min.

**Architecture:** Híbrido em 4 entregas. (1) vocabulário do Tibia na transcrição + linha "Entendi"; (2) `entendedor.py` (texto → `Resultado` com certeza) e `dialogo.py` (confirmação e memória) entre a transcrição e o `Store`; (3) o entendedor passa a usar modelos de frase do `hassil` e gera a gramática offline do Vosk; (4) a IA do Worker recebe glossário, candidatos e contexto. O `Store` não muda.

**Tech Stack:** Python 3.14 (pywebview), `unittest`, Vosk, OpenAI via Cloudflare Worker (`worker.mjs`, testes `node`), `hassil 3.12.1` + `PyYAML` + `unicode-rbnf` (entrega 3).

**Spec:** `docs/superpowers/specs/2026-10-16-assistente-fala-natural-design.md`

## Global Constraints

- Pasta compartilhada com o Codex e outras sessões. **Não fazer commit nem trocar a branch na pasta principal.** Cada entrega termina publicando por uma cópia sincronizada com `origin/develop` (ex.: `Z:\Temp\tibia-voz-jarvis-beta-58dcc289`), com **somente** os arquivos da entrega (AGENTS.md, docs/pipeline-beta.md).
- Testes: `Z:\Temp\tibia-tudo-voice-spike\venv\Scripts\python.exe -X utf8 -B -m unittest <módulo>` (sem pytest). UI: `node test_voz_ui.cjs`, `node test_assistente_ui.cjs`. Worker: `node server/voice-worker/test_worker.mjs`. O CI roda `python -m unittest` (tudo). `test_mirror_native` às vezes falha por tempo: repetir.
- Nenhum áudio, transcrição ou memória do diálogo é persistido.
- Teto de gasto atual (US$ 0,20/dia global, US$ 0,05/dia por usuário) não muda. Corpo do `/interpret` ≤ 12000 bytes; do `/transcribe` ≤ 524288 bytes.
- **Deploy do Worker só com "pode" explícito do usuário na hora.**
- Mensagens ao jogador em português do Brasil, curtas.
- Prazo da pergunta pendente: **8 s**. Memória curta: **60 s**. Corte de nome aproximado: **difflib ≥ 0,85** (já usado em `Store._boss`).
- Meta do corpus: **≥ 90%** entendidas sem a IA (entrega 3).

## Review Focus

1. "sim" ou "não" sem pergunta pendente → nada é executado; resposta "Não há nada para confirmar." (Tarefa 5)
2. Troca de personagem durante a pergunta pendente → a pendência é descartada; nunca grava no personagem novo. (Tarefa 5)
3. Cabeçalho de vocabulário inválido (acentos mal codificados, > 40 termos, termo > 40 caracteres) → o Worker transcreve **sem** vocabulário, não falha. (Tarefa 2)
4. Continuação depois da memória expirar ("e o Oberon?" após 61 s) → "Não lembro do assunto; diga o comando completo." (Tarefa 5)
5. Sem internet com pergunta pendente → "sim" e "não" precisam ser reconhecidos pelo Vosk offline. (Tarefa 6: as palavras entram na gramática)

---

## Entrega 1 — Ouvir melhor + "Entendi"


### Progresso em 16/10/2026

- **Tarefas 1–3 concluídas:** vocabulário por personagem/mundo (recentes → bosses com progresso → fixos), cabeçalho opcional e validação tolerante no Worker; prompt no hash e reserva condicional STT de 40000 microUSD, mantendo limites diários; rótulos para todas as ações e linha “Entendi” nos caminhos local, IA e tela, sem repetir execução no Store.
- **Validação focada:** `test_vocabulario`, `test_remote_ai_client`, `test_voz`, `test_assistente_tibiano` e `test_voice_domain_intents`: 96 casos, 95 aprovados na rodada final e uma fixture de contexto corrigida com reexecução direcionada aprovada. `test_worker.mjs`: 32 aprovados. `test_voz_ui.cjs` e `test_assistente_ui.cjs`: aprovados. Testes sem microfone, som real ou chamadas ao provedor.
- **Lacuna conhecida para o corpus da Entrega 3:** “quantos drumi eu ja matei” não é reconhecida pelo parser local atual. O teste de contexto usa “quantas kills tenho no Drume”, já suportada. Não foi ampliada a semântica do parser nesta entrega.
- **Publicação pendente:** implementação congelada para revisão; suíte completa, aprovação explícita/deploy do Worker e publicação Beta da Tarefa 4 continuam com a coordenação. Entregas 2–4 não iniciadas.


### Tarefa 1: Vocabulário no cliente

**Files:**
- Create: `voice/vocabulario.py`
- Modify: `voice/remote_ai_client.py` (`RemoteAIClient.transcribe`, `_post`)
- Modify: `voz.py` (`Servico.receber_audio`, `Servico.comando`)
- Test: `test_vocabulario.py` (novo), `test_remote_ai_client.py`

**Interfaces:**
- Produces: `vocabulario.TERMOS_FIXOS: tuple[str, ...]` (inclui exatamente "Tibia Tudo", "stamina", "shared", "Bosstiary", "boss", "Market", "Tibia Coin", "Gold Token", "Silver Token", "timer"); `vocabulario.montar(com_kills: list[str], recentes: list[str], limite: int = 40) -> list[str]` (ordem: recentes, depois com_kills, depois fixos; sem duplicatas sem diferenciar maiúsculas; corta em `limite`; cada termo ≤ 40 caracteres); `vocabulario.cabecalho(termos: list[str]) -> str` (base64url, sem `=`, de `json.dumps(termos, ensure_ascii=False)`); `RemoteAIClient.transcribe(wav, request_id, vocabulario=())` envia o cabeçalho `X-Vocabulary` só quando houver termos.
- Produces (voz.py): `Servico._recentes: dict[str, float]` (nome do boss → `time.monotonic()` do último uso; expira em 3600 s), atualizado sempre que um intent com `boss_id` é executado (nome resolvido em `result['boss']['name']`).

- [ ] **Step 1: Testes que falham** — `test_vocabulario.py`: `montar(['Drume'], ['Grand Master Oberon'])[:2] == ['Grand Master Oberon', 'Drume']`; `len(montar([f'b{i}' for i in range(100)], [])) == 40`; termo de 60 caracteres é descartado; `json.loads(base64.urlsafe_b64decode(cabecalho(['Ahau','Scarlett Etzel'])+'=='))` devolve a lista. Em `test_remote_ai_client.py`: com um opener falso, `transcribe(wav, rid, ['Drume'])` envia `X-Vocabulary`; `transcribe(wav, rid)` não envia.
- [ ] **Step 2: Rodar** `... -m unittest test_vocabulario test_remote_ai_client` → FAIL (módulo inexistente).
- [ ] **Step 3: Implementar** `voice/vocabulario.py` e o parâmetro em `transcribe` (`_post` ganha `extra_headers: dict | None = None`).
- [ ] **Step 4: Ligar em `voz.py`:** antes de `client.transcribe`, montar `com_kills` = nomes com `progress > 0` de `store.execute('boss.cooldown.list', {}, contexto)['bosses']` (try/except → `[]`) e `recentes` = chaves válidas de `_recentes`. Teste em `test_voz.py`: com um store que tem kill de Drume, `client.transcribe.call_args` recebe `'Drume'` no vocabulário.
- [ ] **Step 5: Rodar** `... -m unittest test_vocabulario test_remote_ai_client test_voz test_assistente_tibiano` → OK.

### Tarefa 2: Worker usa o vocabulário (e revisão do glossário pendente)

**Files:**
- Modify: `server/voice-worker/worker.mjs` (rota `/transcribe`, ~linha 126; cálculo de `payloadHash`)
- Test: `server/voice-worker/test_worker.mjs`

**Interfaces:**
- Consumes: cabeçalho `X-Vocabulary` (Tarefa 1).
- Produces: com o cabeçalho válido, `FormData` ganha `prompt = 'Termos do Tibia: ' + termos.join(', ')`. Inválido (base64 ruim, JSON ruim, > 40 termos, termo vazio ou > 40 caracteres, caractere fora de letras/números/espaço/`'`/`-`/`.`) → **sem** `prompt`, sem erro. O vocabulário entra no `payloadHash` (mesmo `request_id` com outro vocabulário = conflito, igual ao corpo).

- [ ] **Step 1: Testes que falham** em `test_worker.mjs`: (a) cabeçalho válido → o fetch falso para a OpenAI recebe `prompt` contendo `Drume`; (b) 41 termos → sem `prompt` e status 200; (c) base64 inválido → sem `prompt` e 200; (d) mesmo `request_id` repetido com outro vocabulário → mesma regra de conflito que já existe para corpo diferente.
- [ ] **Step 2: Rodar** `node server/voice-worker/test_worker.mjs` → os 4 novos falham.
- [ ] **Step 3: Implementar** `parseVocabulary(header: string | null): string[] | null` no `worker.mjs` e usar na rota.
- [ ] **Step 4: Revisar o glossário `NLU_INSTRUCTIONS`** que a sessão interrompida escreveu (diff contra a cópia de publicação). Confirmar que o corpo completo de `/interpret` com o glossário cabe em 12000 bytes (o teste existente cobre). Se o texto estiver correto, mantém e entra neste deploy; se não, reverter para o texto da cópia de publicação e anotar para a Tarefa 11.
- [ ] **Step 5: Rodar** `node server/voice-worker/test_worker.mjs` → todos passam.

### Tarefa 3: "Entendi" na tela

**Files:**
- Modify: `assistente_tibiano.py` (nova `describe`)
- Modify: `voz.py` (`Servico.__init__`, `comando`, `_intent_reply`, `estado`)
- Modify: `web/index.html` (bloco "Último comando", ~linha 1024), `web/voz.js` (`render`)
- Test: `test_assistente_tibiano.py`, `test_voz.py`, `test_voz_ui.cjs`

**Interfaces:**
- Produces: `assistente_tibiano.LABELS: dict[str, str]`, com rótulo humano para **toda** chave de `FIELDS` (ex.: `'boss.kill': 'Registrar abate'`, `'stamina.time_to': 'Quando a stamina chega a'`, `'timer.create': 'Criar timer'`). `describe(intent: str, args: dict) -> str` = rótulo + ` · ` + os valores relevantes em linguagem humana (boss pelo nome; minutos de stamina como `41h00`; duração como `5 min`). `Servico.estado()['entendi']: str` (vazio até o primeiro comando). `#voz-entendi` na tela.

- [ ] **Step 1: Testes que falham:** `set(LABELS) == set(FIELDS)`; `describe('stamina.time_to', {'target_stamina_minutes': 2520}) == 'Quando a stamina chega a · 42h00'`; `describe('boss.kill', {'boss_id': 'drume'})` contém `Registrar abate`; em `test_voz.py`, depois de `comando('timer de 30 segundos')`, `estado()['entendi']` contém `Criar timer`; em `test_voz_ui.cjs`, `render({..., entendi: 'Criar timer · 30 s'})` preenche `#voz-entendi`.
- [ ] **Step 2: Rodar** → FAIL.
- [ ] **Step 3: Implementar** `LABELS`, `describe` e `self._entendi` em `voz.py` (definido no caminho local e no caminho da IA). HTML: `<p><b>Entendi:</b> <span id="voz-entendi">—</span></p>` entre "Ouvi" e "Resposta".
- [ ] **Step 4: Rodar** os três testes → OK.

### Tarefa 4: Publicar a entrega 1

- [ ] **Step 1:** Suíte completa na pasta principal (unittest + os 3 testes node) → OK.
- [ ] **Step 2:** Pedir ao usuário: "Posso publicar o servidor de voz (Worker) com o vocabulário?" e esperar o "pode". Com o ok: `wrangler deploy` em `server/voice-worker/`. Conferir com uma chamada real curta de `/transcribe` (áudio sintético já usado pelos testes de validação) que retorna 200.
- [ ] **Step 3:** Na cópia de publicação: `git fetch` + `git merge --ff-only origin/develop`. Copiar **somente** `voice/vocabulario.py`, `test_vocabulario.py`, `voice/remote_ai_client.py`, `test_remote_ai_client.py`, `voz.py`, `test_voz.py`, `assistente_tibiano.py`, `test_assistente_tibiano.py`, `web/index.html`, `web/voz.js`, `test_voz_ui.cjs`, `server/voice-worker/worker.mjs`, `server/voice-worker/test_worker.mjs`, mais a spec e este plano. Conferir `git diff --stat`: só o que esta entrega mudou.
- [ ] **Step 4:** Suíte completa na cópia → OK. Commit (mensagem em arquivo, `git commit -F`, com o `Co-Authored-By`) + `git push origin develop`.
- [ ] **Step 5:** `gh run watch <id> --exit-status` em segundo plano. Confirmar a release `v1.0.31-beta.N.1` com `ZandaoTibiaToolsBetaSetup.exe` e mandar o link ao usuário, pedindo um teste com microfone (falar 3 frases da aba Instruções e 3 do jeito dele) e o que apareceu em "Ouvi" e "Entendi".

---

## Entrega 2 — Pergunta por voz + memória curta

### Tarefa 5: `resolve_boss`, `entendedor.py` (v1) e `dialogo.py`

**Files:**
- Modify: `assistente_tibiano.py` (extrair `resolve_boss` de `Store._boss`)
- Create: `entendedor.py`, `dialogo.py`
- Test: `test_entendedor.py`, `test_dialogo.py` (novos)

**Interfaces:**
- Produces: `assistente_tibiano.resolve_boss(catalog: list[dict], identity: str) -> tuple[dict | None, str, list[str]]` = (boss, certeza, nomes candidatos). Certeza: `'alta'` (chave exata ou palavras contidas, único), `'media'` (difflib ≥ 0,85, único), `'baixa'` (2+ candidatos), `'nenhuma'`. `Store._boss` passa a usar essa função e mantém **as mesmas mensagens de erro** de hoje.
- Produces: `entendedor.Resultado` (dataclass): `intent: str | None`, `args: dict`, `certeza: str` (`'alta'|'media'|'baixa'`), `candidatos: list[str]`, `origem: str` (`'regras'|'modelos'|'ia'|'memoria'`), `erro: str | None = None`. `entendedor.entender(texto: str, agora: datetime, catalogo: list[dict]) -> Resultado`. Na v1 usa `assistente_tibiano.parse`: `ValueError` → `erro`; `None` → `intent=None`; se houver `boss_id`, usa `resolve_boss` (média → troca `boss_id` pelo id resolvido; baixa → `candidatos`; nenhuma → `erro` com a mensagem de `Store._boss`).
- Produces: `dialogo.READ_ONLY: frozenset[str]` (exatamente: `history`, `shared.range`, `shared.check`, `shared.party_range`, `timer.list`, `timer.get`, `boss.catalog`, `boss.cooldown.get`, `boss.cooldown.list`, `bosstiary.get`, `stamina.get`, `stamina.project`, `stamina.time_to`, `stamina.reverse`, `market.stats`, `market.watch.list`, `market.alert.list`). `dialogo.Acao` (dataclass): `tipo: str` (`'executar'|'perguntar'|'falar'`), `intent: str | None = None`, `args: dict = field(default_factory=dict)`, `texto: str = ''`. Classe `dialogo.Dialogo`:
  - `decidir(res: Resultado, agora: float, personagem: str) -> Acao` — alta → executar; média + intent que grava → perguntar `"Você quis dizer {descrição}? Sim ou não?"` (guarda pendência); média + consulta → executar; baixa → perguntar `"Qual boss: A ou B?"` (até 3 nomes; guarda pendência que espera um nome).
  - `responder(texto: str, agora: float, personagem: str) -> Acao | None` — só com pendência válida (≤ 8 s e mesmo personagem). `sim|isso|pode|confirma|confirmo|certo` → executar; `nao|não|cancela|deixa` → falar `"Tudo bem, nada feito."`; pendência de nome + texto que `resolve_boss` resolve com certeza alta/média → executar com o boss. Outra coisa → descarta a pendência e devolve `None`. Sem pendência e texto for só sim/não → falar `"Não há nada para confirmar."`.
  - `lembrar(intent: str, args: dict, resultado: dict, agora: float, personagem: str) -> None`.
  - `continuar(texto: str, agora: float, personagem: str, catalogo: list[dict]) -> Resultado | None` — com memória (≤ 60 s, mesmo personagem): `e (o|a|do|da) X` → mesmo intent com `boss_id=X`; `(mais|aumenta|adiciona) N minutos` → `timer.extend` no último timer; `cancela (ele|esse|o timer)` → `timer.cancel` no último timer; `desfaz` → `boss.kill.undo` (último abate) ou `timer.cancel` (último timer criado); qualquer outro → `None`. Continuação reconhecida sem memória válida → `Resultado(intent=None, erro='Não lembro do assunto; diga o comando completo.')`.
  - `limpar() -> None`.

- [ ] **Step 1: Testes que falham** (`test_entendedor.py`): `'matei o Scarlet Etzel'` → certeza `media`, `args['boss_id']=='scarlett-etzel'`; `'matei o Drume'` → `alta`; `'quanto falta pro Ferumbras'` com 2+ candidatos → `baixa`; `'abc xyz'` → `intent is None`; `'TC tá 1.500'` → `erro` contém `Preço ambíguo`.
- [ ] **Step 2: Testes que falham** (`test_dialogo.py`, relógio passado como número): média + `boss.kill` → `perguntar`; `responder('sim', t+3)` → `executar`; `responder('sim', t+9)` → `None` (expirou); `responder('não')` → `falar 'Tudo bem, nada feito.'`; **Review Focus 1**: `responder('sim')` sem pendência → `falar 'Não há nada para confirmar.'`; **Review Focus 2**: pendência criada para "Elite Nestos", `responder('sim', t+2, 'Outro')` → `None` e a pendência some; baixa → `responder('Ferumbras Mortal Shell')` → executar com esse boss; memória: `lembrar('boss.cooldown.get', {'boss_id':'drume'}, ...)` e depois `continuar('e o Oberon?', t+10, ...)` → intent `boss.cooldown.get`, `boss_id` Oberon; **Review Focus 4**: `continuar('e o Oberon?', t+61, ...)` → `erro 'Não lembro do assunto; diga o comando completo.'`; `continuar('desfaz')` depois de `boss.kill` → `boss.kill.undo`; `continuar('mais 2 minutos')` depois de `timer.create` (resultado com `timer.id`) → `timer.extend` com `delta_seconds=120` e esse `timer_id`.
- [ ] **Step 3: Rodar** `... -m unittest test_entendedor test_dialogo` → FAIL.
- [ ] **Step 4: Implementar** `resolve_boss`, `entendedor.py` e `dialogo.py` conforme as interfaces.
- [ ] **Step 5: Rodar** `... -m unittest test_entendedor test_dialogo test_assistente_tibiano` → OK (os testes de nome de boss existentes continuam verdes).

### Tarefa 6: Ligar o diálogo na voz

**Files:**
- Modify: `voz.py` (`Servico.comando`, `receber_texto`, `receber_audio`, `_intent_reply`, `parar`, `escutar`)
- Modify: `voice/spike_assistente.py` (`recognition_grammar`: acrescentar `sim`, `isso`, `pode`, `confirma`, `deixa`)
- Test: `test_voz.py`, `test_assistente_tibiano.py` (`IntegrationTests`)

**Interfaces:**
- Consumes: `entendedor.entender`, `dialogo.Dialogo` (Tarefa 5), `describe` (Tarefa 3).
- Produces: `Servico._dialogo: Dialogo`. Quando a ação é `perguntar`: `self._command_state['pergunta'] = True` e `self._armed_until = agora + 8`. Enquanto houver pergunta, `receber_texto` aceita qualquer fala sem "Hey Tibia Tudo", e a regra de negação **não** aborta. No `receber_audio`, a pergunta pendente **não** força o caminho local (só o estado legado `'cancel'` força); a resposta pode ir para a transcrição online. Resultado da IA (`_intent_reply`) entra como `Resultado(origem='ia', certeza='media')` e passa por `decidir`. Troca de personagem (contexto diferente do da pendência), `parar()` e `escutar()` chamam `_dialogo.limpar()`. Falha online (`RemoteAIError`, incluindo limite diário): a **primeira** da sessão prefixa a resposta local com `"Sem internet, usando o modo offline. "`; as seguintes usam o modo local sem repetir o aviso (`Servico._aviso_offline: bool`, zera quando uma chamada online volta a funcionar).

- [ ] **Step 1: Testes que falham** (store real em pasta temporária, como em `IntegrationTests`): "matei o Scarlet Etzel" → resposta contém `Você quis dizer` e **nenhum** abate gravado; em seguida `receber_texto('sim')` (sem wake) → 1 abate de Scarlett Etzel; "quanto falta pro Drume" seguido de "e o Oberon?" → resposta sobre o Oberon; IA devolvendo `boss.kill` → pergunta antes de gravar; duas falhas online seguidas → só a primeira resposta começa com `Sem internet, usando o modo offline.`; **Review Focus 5**: `'sim' in recognition_grammar()` e `'isso' in recognition_grammar()`.
- [ ] **Step 2: Rodar** `... -m unittest test_voz test_assistente_tibiano` → FAIL.
- [ ] **Step 3: Implementar** a integração conforme as interfaces.
- [ ] **Step 4: Rodar** a suíte completa → OK (os testes atuais de voz continuam verdes).

### Tarefa 7: Publicar a entrega 2

- [ ] Igual à Tarefa 4, Steps 1 e 3–5 (sem deploy do Worker). Arquivos: `assistente_tibiano.py`, `entendedor.py`, `dialogo.py`, `voz.py`, `voice/spike_assistente.py` e os testes `test_entendedor.py`, `test_dialogo.py`, `test_voz.py`, `test_assistente_tibiano.py`. Na aba Instruções (`web/index.html`), acrescentar no card Bosses as frases `e o Oberon` e `desfaz`. O teste de frases da aba precisa aceitar essas duas: elas só valem com memória, então ficam fora do `<q>` (usar `<em>`).

---

## Entrega 3 — Modelos de frase + offline completo

### Tarefa 8: Dependências e empacotamento

**Files:**
- Modify: `requirements-build.lock`, `build.bat`, `instalador/gerar_instalador.ps1`, `packaging-resources.json`, `package_tools.py` (se necessário)
- Test: `test_package_delivery.py`

**Interfaces:**
- Produces: `hassil==3.12.1`, `PyYAML` e `unicode-rbnf` (versões compatíveis com o hassil 3.12.1 e com wheel para Python 3.14 no Windows) no lock **com hashes** (`python -m pip download <pkg>==<ver> --no-deps --only-binary=:all:` + `python -m pip hash`). `voice/frases_pt.yaml` empacotado em `voice/` nos dois builds (como já é feito com `voice/domain_actions.json`) e listado em `packaging-resources.json`.

- [ ] **Step 1:** Teste que falha em `test_package_delivery.py`: o manifesto exige `voice/frases_pt.yaml` (mesmo padrão do teste que já existe para `domain_actions.json`).
- [ ] **Step 2:** Implementar (lock, `--add-data` nos dois scripts de build, manifesto) e instalar no venv de testes: `... -m pip install --require-hashes -r <trecho do lock>`.
- [ ] **Step 3:** `... -m unittest test_package_delivery` → OK.

### Tarefa 9: `frases_pt.yaml`, corpus e entendedor v2

**Files:**
- Create: `voice/frases_pt.yaml`, `voice/frases_teste.yaml`
- Modify: `entendedor.py`
- Test: `test_entendedor.py`

**Interfaces:**
- Consumes: `Resultado`, `entender` (Tarefa 5) — **mesma assinatura**.
- Produces: `frases_pt.yaml` no formato do hassil (`language: pt-BR`, `intents`, `lists`, `expansion_rules`, `skip_words`). Os nomes de intent são **as chaves de `FIELDS`** (ex.: `boss.kill`). Listas: `boss` (preenchida em tempo de execução com nomes e apelidos do catálogo via `TextSlotList.from_strings`), `item` (watchlist + `Tibia Coin`, `Gold Token`, `Silver Token`), `horas`/`minutos`/`segundos`/`level`/`kills` (`range`, `words: true`, `words_language: pt`), `rotulo` (wildcard). `skip_words` incluem pelo menos `por favor`, `pode`, `aí`, `eu`, `ok`. `entendedor.carregar_modelos(caminho: Path) -> hassil.Intents` (com cache por processo). `entender` tenta o `hassil.recognize(...)` primeiro (`origem='modelos'`) e cai no `parse` atual (`origem='regras'`) quando nada bate. As durações e datas convertidas usam as mesmas funções de `assistente_tibiano` (`local_datetime` e a conversão de `duration`).
- Produces: `voice/frases_teste.yaml` = lista de `{fala, intent, args}` com ~100 falas naturais. Tem que incluir: "Quando minha estamina estará cheia?", "Vou fazer logout agora, minha estamina está em quarenta e uma horas.", "matei o drumi", "bota um timer de cinco minutos", "quanto tempo falta pro Oberon", "tenho oitenta e sete kills do Oberon", "qual é minha stamina", "TC tá 36.5k", e pelo menos 5 falas por grupo da aba Instruções.

- [ ] **Step 1: Testes que falham:** `test_corpus_sem_ia`: proporção de falas do corpus com `entender(...).origem == 'modelos'` e `(intent, args)` igual ao esperado ≥ **0,90**; `test_instrucoes_continuam`: o teste de frases da aba + variações continua verde usando `entender` (não só `parse`); `test_numero_por_extenso`: `'timer de quarenta e cinco minutos'` → `duration_seconds == 2700` vindo de `modelos`.
- [ ] **Step 2: Rodar** `... -m unittest test_entendedor` → FAIL.
- [ ] **Step 3: Escrever** `frases_pt.yaml` (começar pelas regras de expansão: `<timer>`, `<matar>` = `(matei|matamos|derrubei|acabei de matar|fiz)`, `<stamina>` = `(stamina|estamina)`, `<quando>`) e o corpus; implementar `carregar_modelos` e o caminho do hassil em `entender`.
- [ ] **Step 4: Rodar** → OK. Se o corpus ficar abaixo de 0,90, acrescentar modelos (não baixar a meta).

### Tarefa 10: Gramática offline gerada dos modelos

**Files:**
- Modify: `voice/spike_assistente.py` (`recognition_grammar`), `voz.py` (passar o catálogo ao montar o reconhecedor em `_listen`)
- Test: `voice/test_spike_assistente.py`

**Interfaces:**
- Produces: `recognition_grammar(nomes_boss: list[str] = ()) -> list[str]` = frases de ativação + **todas as palavras literais** de `frases_pt.yaml` + palavras dos nomes de boss + números de 0 a 100 por extenso + `sim/não/isso/pode/confirma/cancela/deixa` + `[unk]`. O Vosk recebe palavras soltas, que ele concatena (evita a explosão de combinações). Chamada sem argumentos continua funcionando, para não quebrar os testes atuais.

- [ ] **Step 1: Testes que falham:** `{'matei', 'stamina', 'drume', 'oberon', 'sim', 'quarenta'} <= set(recognition_grammar(['Drume', 'Grand Master Oberon']))`; `len(recognition_grammar(nomes_do_catalogo)) < 6000`.
- [ ] **Step 2: Rodar** `... -m unittest voice.test_spike_assistente` → FAIL.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Rodar** a suíte completa → OK.
- [ ] **Step 5: Publicar a entrega 3** como na Tarefa 4, Steps 1 e 3–5. Arquivos: os das Tarefas 8–10 + `entendedor.py`. Avisar o usuário que o modo offline agora entende todos os comandos dos modelos.

---

## Entrega 4 — IA com descrições, candidatos e contexto

### Tarefa 11: `/interpret` com candidatos e contexto

**Files:**
- Modify: `server/voice-worker/worker.mjs` (validação do corpo de `/interpret`, ~linha 120; `NLU_INSTRUCTIONS`), `voice/remote_ai_client.py` (`interpret`), `voice/domain_actions.json` (se faltar `boss.cooldown.set` ou `stamina.get`), `voz.py` (chamada de `interpret`)
- Test: `server/voice-worker/test_worker.mjs`, `test_remote_ai_client.py`, `test_voice_domain_intents.py`

**Interfaces:**
- Produces: corpo de `/interpret` = `{request_id, text}` mais os campos opcionais `candidatos: string[]` (≤ 5, cada um ≤ 80 caracteres) e `contexto: {intent: string, boss: string | null}` (o `intent` precisa existir no catálogo). O Worker acrescenta à entrada do modelo `Candidatos: …` e `Assunto anterior: …`. Campo desconhecido ou inválido → 400, como hoje. `RemoteAIClient.interpret(text, request_id, candidatos=(), contexto=None)`. O `voz.py` envia `candidatos` = até 5 nomes de boss de `resolve_boss`/difflib sobre o texto, e `contexto` = memória do `Dialogo`, se houver.

- [ ] **Step 1: Testes que falham:** Worker aceita os dois campos opcionais e os coloca na entrada enviada à OpenAI; rejeita 6 candidatos e `contexto.intent` fora do catálogo; o corpo completo com glossário + 5 candidatos + contexto continua ≤ 12000 bytes. Cliente: `interpret('…', rid, ['Drume'], {'intent': 'boss.cooldown.get', 'boss': 'Drume'})` envia esses campos. `test_voice_domain_intents.py`: toda chave de `FIELDS` que a IA pode devolver tem schema em `domain_actions.json` (lista explícita das excluídas: `boss.catalog.import`, `history`).
- [ ] **Step 2: Rodar** os três conjuntos de testes → FAIL.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Rodar** → OK.
- [ ] **Step 5: Publicar a entrega 4** como na Tarefa 4 (com deploy do Worker após o "pode" do usuário). Ao final, revisão de todo o conjunto (`superpowers:requesting-code-review`) e encerramento da sessão "Melhorar instruções da IA de voz no Worker" (o trabalho dela foi absorvido aqui).


## Coordenação — validação e publicação da Entrega 1 (16/10/2026)

- Base conferida: Beta89, commit0a4716393c9745839f8adbcdc064ee2e89ba395d. As entregas anteriores do Claude foram preservadas.
- Contrato sincronizado com os schemas pendentes stamina.get e boss.cooldown.set; testes do cliente e do Worker aprovados.
- Validação:729 testes Python completos;86 testes focados após ajuste final que impede uma ação manual de alterar Ouvi/Entendi/Resposta.
- Usuário autorizou expressamente publicar o Worker. Deploy186fc50e-2c14-42aa-89f1-da168ca37195 concluído; STT real com áudio sintético em memória reconheceu Drume e NLU real retornou stamina.get. Nenhuma gravação de domínio, áudio ou transcrição persistida.
- Teto globalUS$0,20/dia preservado. Limite individual padrão versionadoUS$0,05; override operacional de testeUS$0,10 já existente foi mantido.
- Beta90 compilou/publicou com sucesso (run38974415758); a correção final do diagnóstico manual segue para nova Beta. Confirmar a tag e os artefatos no pipeline antes da entrega.
- Entregas2–4 (diálogo/memória/modelos/contexto NLU) ainda não iniciadas nesta retomada.
