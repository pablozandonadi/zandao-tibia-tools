# Aba Admin: códigos da IA por pessoa — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O dono gera, lista, limita e revoga códigos de acesso da IA por pessoa numa aba Admin (só na Beta), com os códigos guardados no servidor e amarrados a 2 PCs.

**Architecture:** O Worker `tibia-tudo-voz` ganha duas tabelas no SQLite do Durable Object `VoiceGate` (`tokens`, `devices`), rotas `/admin/*` protegidas por uma senha de admin (hash em secret) e um segundo passo de autenticação que consulta essas tabelas depois da lista fixa `VOICE_TOKENS_JSON`, que continua valendo. O app envia um ID de instalação, mostra mensagens novas de erro e ganha um módulo cliente de admin, funções em `web_api.py` recusadas fora do canal Beta e uma página Admin.

**Tech Stack:** Cloudflare Worker (JS, `node --test`, `node:sqlite`), Python 3.14 `unittest` (stdlib `urllib`, DPAPI via `voz_credenciais`), HTML/JS do app (`web/`), testes de tela em Node (`*.cjs`).

**Spec:** `docs/superpowers/specs/2026-10-19-admin-codigos-ia-design.md` (os executores leem os dois).

## Global Constraints

- `subject`: `^[a-zA-Z0-9_-]{1,80}$`. Código e senha de admin: 32 bytes aleatórios em base64url = **43 caracteres** `[A-Za-z0-9_-]`. O servidor guarda só o SHA-256 em hex minúsculo.
- Padrões: `VOICE_DEVICES_MAX = 2`, `VOICE_ADMIN_BURST_LIMIT = 10` (por IP por minuto). Secret novo: `ADMIN_TOKEN_HASH`.
- Planos: `mode` ∈ `daily` | `total` | `unlimited`; `quota` inteiro ≥ 1 em `daily`/`total` e ausente em `unlimited`; `expires` em milissegundos, opcional, no futuro ao gravar. Dia = **dia UTC** (`Math.floor(Date.now()/86400000)`, como os buckets atuais).
- Erros de **admin**: corpo sempre `{"error":"voice_unavailable"}`. Erros de **usuário** específicos só depois de o código ser reconhecido: `{"error":"device_limit"}` (403), `{"error":"code_expired"}` (403), `{"error":"quota_exhausted","limit_reason":"token_total"|"token_daily"}` (429).
- Códigos antigos (`VOICE_TOKENS_JSON`) mantêm o comportamento atual: sem `X-Device-ID`, limites `VOICE_USER_*`.
- Textos de erro do app (Português, exatos): "Este código já está em uso em outros computadores. Peça um novo ao administrador." / "Este código expirou. Peça um novo ao administrador." / "O limite de uso deste código acabou. Peça mais ao administrador."
- Arquivos novos privados: `voice-device.id` (não é segredo, não vai em pacote) e `admin-online.dpapi` (+ `.tmp`), ambos na pasta de dados do canal.
- A aba Admin e toda função de admin do app só funcionam com `CANAL_APP == 'beta'`.
- **Nenhum `git push` e nenhuma publicação de Beta** até o dono mandar. Um commit local por tarefa.
- Comandos: Python `py -m unittest <modulo>`; Worker `node --test server/voice-worker/test_worker.mjs`; telas `node test_<nome>.cjs` (use `Y:\node.exe` se `node` não estiver no PATH).

## Review Focus

1. Duas gerações simultâneas para o mesmo `subject`: exatamente uma vira 201 e a outra 409 (Task 2).
2. A N-ésima requisição passa e a N+1 recebe 429; N requisições simultâneas no limite deixam passar só as que cabem; repetir o mesmo `X-Request-ID` (409) não conta duas vezes (Task 4).
3. Senha de admin errada, ausente ou com `Origin` não revelam se o código/rota existe, e tentativas repetidas são limitadas por IP (Task 2).
4. `X-Device-ID` em maiúsculas é o mesmo PC que em minúsculas (não consome a 2ª vaga); ausente ou inválido dá 400 só para código novo (Task 3).
5. A senha de admin e os códigos gerados nunca aparecem em exceção, log nem retorno de estado do app (Tasks 6 e 7).

---

### Task 1: Base do Worker — config opcional, tabelas e `identify`

**Files:**
- Modify: `server/voice-worker/worker.mjs` (função `config` ~l.8-18, `authenticate` ~l.19-23, construtor de `VoiceGate` ~l.94-97, `fetch` externo ~l.91, `VoiceGate.fetch` ~l.134)
- Test: `server/voice-worker/test_worker.mjs`

**Interfaces:**
- Produces: `config(env)` passa a devolver também `DEVICES_MAX: number` (padrão 2 se `VOICE_DEVICES_MAX` ausente; se presente, inteiro positivo ou 503) e `values.tokens = {}` quando `VOICE_TOKENS_JSON` é `undefined` (se presente, a validação atual não muda). `async function identify(request, env, cfg): Promise<{hash: string, subject: string|null}>` (formato `Bearer` inválido → `fail(401)`; `subject` vem da lista fixa ou `null`). Tabelas `tokens(hash TEXT PRIMARY KEY, subject TEXT NOT NULL, created INTEGER NOT NULL, revoked INTEGER, mode TEXT NOT NULL, quota INTEGER, expires INTEGER, used_total INTEGER NOT NULL DEFAULT 0)` e `devices(hash TEXT NOT NULL, device_id TEXT NOT NULL, first_seen INTEGER NOT NULL, last_seen INTEGER NOT NULL, PRIMARY KEY(hash, device_id))`, criadas com `CREATE TABLE IF NOT EXISTS`.

- [ ] **Step 1: Escrever os testes que falham** em `test_worker.mjs`:
  - `'sem VOICE_TOKENS_JSON o servidor não cai: token desconhecido dá 401'`: `setup({VOICE_TOKENS_JSON: undefined})`; `assert.equal((await s.req()).status, 401)`.
  - `'as tabelas tokens e devices existem'`: `s.db.prepare("SELECT name FROM sqlite_master WHERE name IN ('tokens','devices')").all().length === 2`.
  - `'VOICE_DEVICES_MAX inválido falha fechado'`: `setup({VOICE_DEVICES_MAX:'0'})` → `(await s.req()).status === 503`.
- [ ] **Step 2: Rodar e ver falhar** — `node --test server/voice-worker/test_worker.mjs` (os 3 novos falham, o resto passa).
- [ ] **Step 3: Implementar** as assinaturas acima. `identify` substitui `authenticate` nos dois pontos de uso; na `VoiceGate.fetch`, `subject = id.subject ?? fail(401)` (a Task 3 troca isso pela consulta à tabela). Nada muda para quem já tem código antigo.
- [ ] **Step 4: Rodar a suíte inteira do Worker** — Expected: tudo passa, inclusive os testes antigos.
- [ ] **Step 5: Commit** — `git add server/voice-worker && git commit -m "Worker: tabelas de códigos, DEVICES_MAX e identify()"`

---

### Task 2: Rotas de admin (gerar, listar, revogar, alterar limite)

**Files:**
- Modify: `server/voice-worker/worker.mjs` (export default `fetch`; `VoiceGate.fetch`; métodos novos)
- Test: `server/voice-worker/test_worker.mjs`

**Interfaces:**
- Consumes: tabelas e `hash()` da Task 1.
- Produces (todas em `VoiceGate`): `async adminFetch(request): Promise<Response>`; `createToken(subject, plan): {token, subject, mode, quota, expires, devices_max, created}`; `listTokens(): Array<{subject, created, revoked, mode, quota, expires, used_total, devices, last_seen, today_requests}>`; `revokeToken(subject): number`; `updateLimit(subject, plan, resetUsed): number`. Função pura `normalizePlan(body, now): {mode, quota, expires}` (lança `fail(400)` para combinação inválida: `quota` em `unlimited`, `quota` ausente/≤0/não inteira em `daily`/`total`, `mode` desconhecido, `expires` não inteiro ou ≤ `now`).
- Roteamento: o `fetch` externo manda qualquer `pathname` começando em `/admin/` direto ao Durable Object, **sem** `config()` (admin funciona com a IA desligada), depois do teste de HTTPS. Erros viram `{"error":"voice_unavailable"}` com o status.
- Ordem em `adminFetch`: HTTPS (403) → cabeçalho `Origin` presente (**403**) → `ADMIN_TOKEN_HASH` ausente (503) → rajada por IP (bucket `burst-admin:{ipHash}:{minuto}`, limite `VOICE_ADMIN_BURST_LIMIT`, padrão 10, 429) → senha (`Authorization: Bearer <43>`; hash comparado em **tempo constante**, laço XOR sobre as duas strings hex; senão 401) → rota/método (`POST /admin/tokens`, `GET /admin/tokens`, `POST /admin/tokens/revoke`, `POST /admin/tokens/limit`; outro caminho 404).
- `createToken`: 32 bytes de `crypto.getRandomValues`, base64url sem `=`; dentro de `transactionSync`, 409 se já existe linha com o mesmo `subject` e `revoked IS NULL`. `revokeToken` seta `revoked = Date.now()` em todos os ativos do `subject` (0 linhas → 404). `updateLimit` aplica `normalizePlan` ao código ativo (404 se não houver) e, com `resetUsed: true`, zera `used_total`. `today_requests` = `count` do bucket `u:{subject}:{diaUTC}` (0 se não existe).

- [ ] **Step 1: Escrever os testes que falham.** Helper no arquivo: `const adminToken='c'.repeat(43)`; `setup({ADMIN_TOKEN_HASH: await digest(adminToken)})`; `adm(s,path,{method='POST',body,token=adminToken,headers={}})` que chama `worker.fetch(new Request('https://voice.example'+path,{method,headers:{authorization:'Bearer '+token,'content-type':'application/json',...headers},body:body&&JSON.stringify(body)}))`. Testes:
  - `'admin sem ADMIN_TOKEN_HASH responde 503'`.
  - `'senha errada, ausente e com Origin são recusadas'`: 401, 401, 403, corpo igual `{error:'voice_unavailable'}`.
  - `'gerar devolve código de 43 caracteres e grava só o hash'`: 201; `body.token` casa `/^[A-Za-z0-9_-]{43}$/`; `s.db.prepare('SELECT hash FROM tokens').get().hash === await digest(body.token)`; nenhuma coluna de `tokens` contém `body.token`.
  - `'duas gerações simultâneas para o mesmo subject: uma 201 e uma 409'` (`Promise.all`); depois de `revoke`, gerar de novo dá 201.
  - `'listar não expõe código nem hash'`: `JSON.stringify(lista)` não contém o token nem o hash.
  - `'planos inválidos dão 400'` para `{mode:'unlimited',quota:5}`, `{mode:'daily'}`, `{mode:'daily',quota:0}`, `{mode:'x'}`, `{mode:'daily',quota:5,expires:1}`.
  - `'alterar limite muda o plano sem trocar o código'` e `'reset_used zera used_total'`.
  - `'tentativas erradas repetidas dão 429'`: `setup({VOICE_ADMIN_BURST_LIMIT:'2', ...})`, 3ª tentativa com senha errada → 429.
- [ ] **Step 2: Rodar e ver falhar** — `node --test server/voice-worker/test_worker.mjs`.
- [ ] **Step 3: Implementar** conforme as Interfaces (blocos legíveis e curtos, separados das funções compactas existentes).
- [ ] **Step 4: Rodar a suíte inteira** — Expected: tudo passa.
- [ ] **Step 5: Commit** — `git commit -m "Worker: rotas /admin para gerar, listar, revogar e limitar códigos"` (adicione os arquivos alterados explicitamente).

---

### Task 3: Autenticação dos códigos novos — tabela, PC e validade

**Files:**
- Modify: `server/voice-worker/worker.mjs` (`VoiceGate.fetch`, métodos novos)
- Test: `server/voice-worker/test_worker.mjs`

**Interfaces:**
- Consumes: `identify`, tabelas, `createToken` (Tasks 1-2), `debitBurst(subject, ip, cfg)` existente.
- Produces: `resolveToken(hash, deviceId, now, cfg): {subject, mode, quota, used_total}` — lança `fail(401)` se o hash não está em `tokens` ou está revogado; `fail(403,{error:'code_expired'})` se `expires` ≤ `now`; `fail(400)` se `deviceId` ausente ou fora de `UUID`; `fail(403,{error:'device_limit'})` se o PC é novo e `COUNT(devices) >= cfg.DEVICES_MAX`. O `device_id` é guardado em **minúsculas**. `debitIpBurst(ip, cfg)`: conta só `burst-ip:{ip}:{minuto}` (mesma chave e limite `IP_BURST_LIMIT` de `debitBurst`) e é chamado **antes** da consulta à tabela quando `identify` devolveu `subject: null`, para código desconhecido não martelar o banco.
- Em `VoiceGate.fetch`: se `identify().subject` existe (lista fixa), segue como hoje, sem `X-Device-ID`; senão `debitIpBurst` → `resolveToken(hash, request.headers.get('X-Device-ID'), Date.now(), cfg)` e usa o `subject` retornado.

- [ ] **Step 1: Escrever os testes que falham.** Helper `novoCodigo(s, subject, plan={mode:'unlimited'})` que gera pela rota admin e devolve o token; `reqCom(s, token, device)` que faz uma requisição `/transcribe` válida com `authorization` e `X-Device-ID`. Testes:
  - `'código novo autentica e grava o PC'`: 200; `devices` tem 1 linha.
  - `'3º PC recebe 403 device_limit; PC já registrado continua'` (com `DEVICES_MAX=2`): corpo `{error:'device_limit'}`.
  - `'X-Device-ID em maiúsculas é o mesmo PC'`: 2 PCs distintos + o primeiro em maiúsculas → continua 200 e `COUNT(*) === 2`.
  - `'X-Device-ID ausente ou inválido dá 400 só para código novo'`; código da lista fixa sem o cabeçalho dá 200.
  - `'código revogado dá 401 na requisição seguinte'`.
  - `'código vencido dá 403 code_expired'`: gravar `expires` no passado direto em `s.db` depois de gerar.
  - `'token desconhecido consome rajada por IP e dá 401'`: `IP_BURST_LIMIT=2` → 401, 401, 429.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar** `resolveToken`, `debitIpBurst` e o ramo em `VoiceGate.fetch`. Em `catch`, o corpo de erro já faz `{error:'voice_request_failed', ...details}`, então `details.error` substitui o `error` padrão sem mudar o `catch`.
- [ ] **Step 4: Rodar a suíte inteira** — Expected: tudo passa.
- [ ] **Step 5: Commit** — `git commit -m "Worker: códigos novos autenticam por tabela, com limite de PCs e validade"` (arquivos explícitos).

---

### Task 4: Planos de uso — `daily`, `total`, `unlimited`

**Files:**
- Modify: `server/voice-worker/worker.mjs` (`reserve`, chamada de `reserve` em `VoiceGate.fetch`)
- Test: `server/voice-worker/test_worker.mjs`

**Interfaces:**
- Consumes: `resolveToken` (Task 3) → `plan = {mode, quota, used_total}` ou `null` para código da lista fixa.
- Produces: `reserve(subject, id, route, payloadHash, duration, cost, ip, cfg, plan = null, hash = null)`. Para o bucket do usuário `u:{subject}:{dia}`:
  - `plan === null` → limites atuais `cfg.USER_DAILY_LIMIT` / `cfg.USER_DAILY_MICRO_USD`.
  - `daily` → limite `plan.quota`; teto de custo `Math.max(cfg.USER_DAILY_MICRO_USD, plan.quota * cfg.NLU_RESERVE_MICRO_USD)`; esgotar dá `fail(429,{error:'quota_exhausted', limit_reason:'token_daily', retry_after_seconds})`.
  - `total` e `unlimited` → o bucket continua contando (para `today_requests`) mas **sem** limite diário por pessoa; em `total`, dentro da mesma `transactionSync`: `used_total >= quota` → `fail(429,{error:'quota_exhausted', limit_reason:'token_total'})`, senão `UPDATE tokens SET used_total = used_total + 1 WHERE hash = ?`.
  - O bucket global `g:{dia}` e o 409 de `X-Request-ID` repetido (que acontece **antes** de contar) não mudam.

- [ ] **Step 1: Escrever os testes que falham** (cada um gera um código com o plano e faz requisições `/transcribe`):
  - `'daily: a N-ésima passa e a N+1 recebe 429 token_daily'` com `quota: 2`, `USER_DAILY_LIMIT: '1'` (prova que o limite do código vale, não o padrão).
  - `'daily acima do teto de custo antigo não é cortado antes de N'`: rota `/interpret` com o provedor simulado dos testes de interpretação existentes (reserva de 2000 µUSD por uso), `NLU_RESERVE_MICRO_USD: '2000'`, `USER_DAILY_MICRO_USD: '50000'` (cabem só 25 usos) e `quota: 30`: os 30 passam e o 31º recebe 429 `token_daily`.
  - `'total: esgota em N, não renova no dia seguinte, volta ao aumentar o limite'`: 429 `token_total`; avançar um dia com `t.mock.method(Date, 'now', () => agora + 86400000)` → continua 429; `updateLimit` com `quota` maior → 200.
  - `'total: reset_used zera e libera de novo'`.
  - `'unlimited passa do limite padrão mas é barrado pelo teto global'`: `USER_DAILY_LIMIT:'1'`, `GLOBAL_DAILY_LIMIT:'3'` → 3 respostas 200 e a 4ª 429 `global_daily_requests`.
  - `'N simultâneas no limite deixam passar exatamente N'`: `Promise.all` de 5 com `quota: 3` → `[200,200,200,429,429]`.
  - `'repetir o mesmo X-Request-ID não conta duas vezes'`: com `total` e `quota: 2`, o mesmo id duas vezes (200 e 409) deixa `used_total === 1`.
  - `'falha do provedor mantém a unidade usada'`: provedor que lança → 502 e `used_total === 1`.
  - `'código antigo continua com os limites USER_*'`.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar** `reserve` com `plan`/`hash` e passar os dois a partir de `VoiceGate.fetch`.
- [ ] **Step 4: Rodar a suíte inteira** — Expected: tudo passa.
- [ ] **Step 5: Commit** — `git commit -m "Worker: planos de uso por código (dia, total, ilimitado)"` (arquivos explícitos).

---

### Task 5: App — ID da instalação e mensagens de erro novas

**Files:**
- Create: `voice/device_id.py`
- Modify: `voice/remote_ai_client.py` (`http_error` ~l.43-62, `RemoteAIClient.__init__` e `_post`), `chat.py` (l.120), `voz.py` (l.59 e l.295)
- Test: `test_remote_ai_client.py`, `test_chat.py`, `test_voice_device_id.py` (novo)

**Interfaces:**
- Produces: `voice.device_id.carregar(pasta: str | Path) -> str` — lê `voice-device.id` da pasta; se não existir ou for inválido, cria com `str(uuid.uuid4())` (escrita atômica por arquivo `.tmp`) e devolve; chamadas seguintes devolvem o mesmo valor. `RemoteAIClient(token: str, device_id: str | None = None)`; quando `device_id` é dado, **todas** as requisições levam `X-Device-ID: <id>`. `http_error(status: int, details: dict | None = None)` passa a tratar `403` com `details['error']` ∈ `{'device_limit','code_expired'}` e `429` com `details['error'] == 'quota_exhausted'`; textos exatos nas Global Constraints; qualquer outro 403/429 mantém os textos atuais. `_post` passa a ler o corpo JSON (≤ 8192 bytes, como já faz no 429) também para o 403.
- Consumers: `chat.py` e `voz.py` criam `RemoteAIClient(token, device_id=device_id.carregar(<pasta de dados>))` — `chat.py` usa `self.pasta`; `voz.py` usa a pasta de dados que já usa para `load_settings`.

- [ ] **Step 1: Escrever os testes que falham.** `test_voice_device_id.py`: `'cria uma vez e reaproveita'` (duas chamadas, mesmo valor, `uuid.UUID(valor).version == 4`); `'arquivo corrompido é refeito'`. `test_remote_ai_client.py`: `'envia X-Device-ID em todas as chamadas'` (cabeçalho capturado no `urlopen` simulado); `'403 device_limit, 403 code_expired e 429 quota_exhausted mostram o texto novo'`; `'403 sem corpo conhecido mantém "bloqueado"'` (o caso já existente na lista de `cases` continua passando).
- [ ] **Step 2: Rodar e ver falhar** — `py -m unittest test_voice_device_id test_remote_ai_client`.
- [ ] **Step 3: Implementar** as assinaturas; `test_chat.py`: um teste de que o `chat.py` entrega o texto de `device_limit` quando o cliente levanta `RemoteAIError`.
- [ ] **Step 4: Rodar** `py -m unittest test_voice_device_id test_remote_ai_client test_chat test_voz` — Expected: OK.
- [ ] **Step 5: Commit** — `git commit -m "App: ID da instalação e mensagens de código esgotado, vencido ou em outros PCs"` (arquivos explícitos).

---

### Task 6: App — cliente de admin e senha protegida

**Files:**
- Create: `admin_ia.py`
- Modify: `app_paths.py` (`PRIVATE_FILES`: acrescentar `'admin-online.dpapi'`, `'admin-online.dpapi.tmp'`), `.gitignore` (acrescentar `admin-online.*`)
- Test: `test_admin_ia.py` (novo), `test_package_delivery.py` (acrescentar os dois nomes à lista da l.46)

**Interfaces:**
- Produces (módulo `admin_ia`, só stdlib, `ENDPOINT = voice.remote_ai_client.ENDPOINT`, sem redirecionamento, timeout 15 s, sem retry): `class AdminIAError(Exception)` com `.status: int | None` e mensagem em Português sem dados sensíveis; `salvar_senha(pasta, senha: str) -> None` (valida `[A-Za-z0-9_-]{43}`; grava com `voz_credenciais._proteger` em `admin-online.dpapi` via `.tmp` + replace); `carregar_senha(pasta) -> str | None`; `limpar_senha(pasta) -> None`; `listar(pasta) -> dict`; `gerar(pasta, subject: str, mode: str, quota: int | None = None, expires: int | None = None) -> dict`; `limite(pasta, subject, mode, quota=None, expires=None, reset_used=False) -> dict`; `revogar(pasta, subject) -> dict`. Cada chamada usa `Authorization: Bearer <senha>`; sem senha salva levanta `AdminIAError('Informe a senha de administrador.')`.
- Mapeamento de status: 401 → "Senha de administrador recusada."; 409 → "Esta pessoa já tem um código ativo. Revogue antes de gerar outro."; 429 → "Muitas tentativas. Aguarde um minuto."; 503 → "Administração indisponível no servidor."; falha de rede → "Sem conexão com o servidor."; demais → "Não foi possível concluir. Tente novamente."

- [ ] **Step 1: Escrever os testes que falham** (`urlopen` simulado e pasta temporária): `'salvar_senha guarda só criptografado'` (o conteúdo de `admin-online.dpapi` não contém a senha em claro); `'senha inválida é recusada antes de gravar'`; `'gerar monta POST /admin/tokens com subject, mode, quota, expires e Authorization'`; `'erros mapeados: 401, 409, 429, 503, rede'`; `'a senha e o código gerado não aparecem na mensagem de nenhuma exceção'` (varrer `str(exc)` e `repr(exc)` dos casos de erro); `'sem senha salva levanta AdminIAError'`; no `test_package_delivery.py`, os dois arquivos novos fazem o pacote falhar se presentes.
- [ ] **Step 2: Rodar e ver falhar** — `py -m unittest test_admin_ia test_package_delivery`.
- [ ] **Step 3: Implementar** as funções acima; o corpo JSON de resposta é validado como `dict` (≤ 64 KiB) antes de devolvido.
- [ ] **Step 4: Rodar** `py -m unittest test_admin_ia test_package_delivery test_app_paths` — Expected: OK.
- [ ] **Step 5: Commit** — `git commit -m "App: cliente de admin da IA com senha protegida por DPAPI"` (arquivos explícitos).

---

### Task 7: App — API do webview e página Admin (só Beta)

**Files:**
- Modify: `web_api.py` (junto de `beta_publicacao_info`, ~l.1625), `web/index.html` (item de menu perto de l.711 e `<section class="page" id="page-admin">` ao lado de `#page-config`), `packaging-resources.json` (acrescentar `"web/admin_ia.js"` após `"web/assistente.js"`)
- Create: `web/admin_ia.js`, `test_admin_ia_ui.cjs`
- Test: `test_web_api_admin_ia.py` (novo), `test_admin_ia_ui.cjs`

**Interfaces:**
- Consumes: `admin_ia.*` (Task 6), `versao.CANAL_APP`, `BASE_DIR` de `web_api.py`.
- Produces em `web_api.py` (métodos da classe da API, retorno `dict`; erro = `{'erro': <mensagem>}` e nunca levanta): `admin_ia_estado()` → `{'beta': bool, 'senha': bool}`; `admin_ia_salvar_senha(senha)`; `admin_ia_listar()`; `admin_ia_gerar(subject, mode, quota, expires)`; `admin_ia_limite(subject, mode, quota, expires, reset_used)`; `admin_ia_revogar(subject)`. Fora do canal beta todas devolvem `{'erro': 'Indisponível neste canal.'}` (exceto `admin_ia_estado`, que devolve `{'beta': False, 'senha': False}`).
- Tela (`web/admin_ia.js`, carregado depois de `chat.js`): item de menu `data-pagina="admin"` com `hidden` por padrão, mostrado só se `api.admin_ia_estado().beta`. Sem senha: só o campo "Senha de administrador" + Salvar. Com senha: tabela (nome, plano, uso, criado, PCs, último uso, situação) com o uso no formato do plano ("12 de 50 hoje" / "30 de 100 no total" / "47 hoje"); formulário Gerar com **Nome**, **Limite de uso** (Ilimitado / N por dia / N no total), **Validade** opcional; por linha **Alterar limite** (com "Zerar pacote" quando `total`) e **Revogar** (confirmação); "Trocar senha". Ao escolher Ilimitado: "Ilimitado ainda respeita o teto global diário do servidor." O código gerado aparece numa caixa com **Copiar** e o aviso "só aparece agora", e some ao fechar; não é guardado em `localStorage` nem em variável global. Exporta `module.exports = {render, gerar}` para o teste, como o `chat.js`.

- [ ] **Step 1: Escrever os testes que falham.** `test_web_api_admin_ia.py`: `'fora do beta todas recusam e nada é gravado'` (patch `versao.CANAL_APP='stable'`, as funções devolvem `erro` e `admin_ia.*` não é chamado); `'no beta repassa os argumentos e devolve erro sem levantar'`; `'estado informa se há senha sem devolvê-la'`. `test_admin_ia_ui.cjs` (mesmo estilo do `test_chat_ui.cjs`): aba oculta quando `beta:false`; sem senha só o campo; o código aparece uma vez e some ao fechar; o texto de uso por plano; confirmação ao revogar.
- [ ] **Step 2: Rodar e ver falhar** — `py -m unittest test_web_api_admin_ia` e `node test_admin_ia_ui.cjs`.
- [ ] **Step 3: Implementar** a API (cada método com `try/except admin_ia.AdminIAError`) e a página; o teste de recursos (`test_package_delivery`/`packaging-resources.json`) exige o arquivo novo na lista.
- [ ] **Step 4: Rodar** `py -m unittest test_web_api_admin_ia test_package_delivery`, `node test_admin_ia_ui.cjs` e `node test_chat_ui.cjs` — Expected: tudo passa. Conferir a tela na prévia local (`preview_start`) com um `api` simulado, nos dois estados (Beta com e sem senha).
- [ ] **Step 5: Commit** — `git commit -m "App: página Admin (Beta) e API de administração dos códigos da IA"` (arquivos explícitos).

---

### Task 8: Documentação do servidor, roteiro de deploy e verificação final

**Files:**
- Modify: `server/voice-worker/README.md` (seção "Operação" passos 3-4 e nova seção "Administração de códigos"), `docs/pipeline-beta.md` (uma linha apontando para o roteiro)
- Test: suíte completa

- [ ] **Step 1:** README: o passo 3 passa a dizer que **os códigos novos nascem na aba Admin da Beta** e que `VOICE_TOKENS_JSON` fica só para os códigos antigos (**não substituir mais** esse segredo); documentar `ADMIN_TOKEN_HASH` (como gerar a senha e o hash com o mesmo `node -e` do README, em terminal privado, guardando a senha num gerenciador), `VOICE_DEVICES_MAX`, `VOICE_ADMIN_BURST_LIMIT`, as quatro rotas `/admin`, os planos `daily`/`total`/`unlimited`, os erros novos e o roteiro de 7 passos da seção 10 do spec, com o teste de fumaça (sem token 401; `GET /admin/tokens` 200 com lista vazia; gerar, usar em 2 PCs, 3º recusado, revogar → 401) e a reversão.
- [ ] **Step 2: Suíte completa**
  - `node --test server/voice-worker/test_worker.mjs` — Expected: tudo passa.
  - `py -m unittest discover -p "test_*.py"` — Expected: OK (o total atual é 828 testes; conferir que nenhum antigo quebrou).
  - `node test_chat_ui.cjs` e `node test_admin_ia_ui.cjs` — Expected: passam.
- [ ] **Step 3: Revisão de segurança** com `ecc:security-reviewer` sobre `worker.mjs` e `admin_ia.py` (senha e códigos fora de logs, comparação em tempo constante, `Origin`, limites). Corrigir o que for apontado e repetir o Step 2.
- [ ] **Step 4: Commit** — `git commit -m "Docs: administração de códigos da IA e roteiro de deploy"`.
- [ ] **Step 5: Parar.** Não fazer push nem publicar Beta. Relatar ao dono: o que mudou, os resultados dos testes e que o deploy do Worker (`wrangler`, login, `ADMIN_TOKEN_HASH`) é o próximo passo dele.
