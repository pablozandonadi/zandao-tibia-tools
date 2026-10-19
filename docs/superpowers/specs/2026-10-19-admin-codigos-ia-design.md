# Aba Admin: códigos de acesso da IA por pessoa (etapa 1)

Data: 19/10/2026. Estado: **spec para revisão** (nada implementado, nada publicado).

## 1. Objetivo

Hoje o chat com IA só funciona com um "código de acesso individual" que o dono do servidor (Worker `tibia-tudo-voz`) gera à mão no terminal e cadastra com `wrangler secret put VOICE_TOKENS_JSON`. Isso é lento, arriscado (cadastrar um token novo substitui o segredo inteiro e derruba os códigos atuais) e não impede que uma pessoa compartilhe o código.

Esta etapa entrega:

1. Uma **aba Admin, somente na Beta**, onde o dono gera, lista e revoga códigos por pessoa.
2. **Códigos guardados no próprio servidor**, sem reescrever o segredo inteiro.
3. **Amarração do código ao computador** (limite de 2 PCs por código) para conter o compartilhamento.
4. Campo `subject` (nome da pessoa) tratado como **id de conta**, para a etapa 2 (contas por usuário) reaproveitar os dados de uso.
5. **Limite de uso escolhido por código, na hora de gerar:** ilimitado, N por dia ou N no total (pacote), com validade opcional, e alterável depois sem trocar o código.

Sucesso: o dono gera um código na Beta em segundos, a pessoa cola em Configurações e usa a IA; um terceiro PC com o mesmo código é recusado; revogar corta o acesso na hora; os códigos que já existem continuam funcionando.

## 2. Decisões aprovadas

- Opção A: administração **no próprio servidor**, com senha de admin própria. O app **não** leva chave do Cloudflare.
- Etapa 1 agora (código por pessoa + amarração ao PC). Contas (Supabase/Kiwify) ficam para o projeto do app pago.
- **A aba Admin só existe na Beta.** Na versão estável a aba não aparece e a API do app recusa qualquer ação de admin. É na Beta que o dono mexe.
- Padrões: **2 PCs por código** e aba visível só na Beta.
- **O admin escolhe o limite de cada código ao gerar** (ilimitado, N por dia ou N no total) e pode alterá-lo depois. Pedido do dono em 19/10/2026; modos `total` e validade opcional foram propostos por mim e aguardam confirmação (ver pergunta de revisão).

## 3. Fora do escopo desta etapa

- Limite por mês e cobrança automática por uso.
- Ligação com a compra (Kiwify) e cadastro por e-mail/senha.
- Editar o número de PCs por código na tela (o valor vem de variável do servidor).
- Proteção contra quem copia a pasta de dados do app (a amarração ao PC não é à prova de fraude; ver riscos).

## 4. Base existente (verificada em `server/voice-worker/worker.mjs` e `voice/remote_ai_client.py`)

- `config(env)` exige `VOICE_AI_ENABLED === 'true'`, todas as variáveis numéricas e **`VOICE_TOKENS_JSON` não vazio**.
- `authenticate()` lê `Authorization: Bearer <43 caracteres base64url>`, calcula o SHA-256 e procura em `cfg.tokens` (hash → identificador). É chamada **duas vezes**: no `fetch` externo e dentro do Durable Object `VoiceGate`.
- O `VoiceGate` (SQLite, instância única `voice-budget`) tem as tabelas `requests` e `buckets`. Cotas diárias usam as chaves `u:{subject}:{dia}` e `g:{dia}`; rajadas, `burst-u:` e `burst-ip:`.
- Rotas de usuário: `POST /transcribe`, `/interpret`, `/chat`.
- O app (`RemoteAIClient`) guarda o código com DPAPI em `voice-online.dpapi` e envia `Authorization`, `X-Request-ID` e `User-Agent`. Erros mapeados em `chat.py`: 401 e 429.

## 5. Servidor

### 5.1 Tabelas novas (no SQLite do `VoiceGate`, `CREATE TABLE IF NOT EXISTS`, sem migração do Durable Object)

```
tokens(hash TEXT PRIMARY KEY, subject TEXT NOT NULL, created INTEGER NOT NULL, revoked INTEGER,
       mode TEXT NOT NULL, quota INTEGER, expires INTEGER, used_total INTEGER NOT NULL DEFAULT 0)
devices(hash TEXT NOT NULL, device_id TEXT NOT NULL, first_seen INTEGER NOT NULL, last_seen INTEGER NOT NULL, PRIMARY KEY(hash, device_id))
```

`subject` segue a regra atual: `^[a-zA-Z0-9_-]{1,80}$`. É o futuro **id de conta**.

### 5.1.1 Limite de uso por código

Cada código novo carrega o seu plano de uso, escolhido pelo admin ao gerar e alterável depois:

| `mode` | `quota` | Significado |
| --- | --- | --- |
| `daily` | N (inteiro ≥ 1) | N usos por dia. O dia segue o dia UTC já usado nos buckets (vira à 21h em Brasília). |
| `total` | N (inteiro ≥ 1) | Pacote: N usos no total. `used_total` conta; ao esgotar, o código para de funcionar até o admin aumentar o limite. |
| `unlimited` | `NULL` | Sem limite próprio de quantidade nem de custo por pessoa. |

- `expires` (milissegundos, opcional): depois dessa data o código para, em qualquer modo.
- "Uso" é uma requisição paga (`/transcribe`, `/interpret` ou `/chat`), a mesma unidade que o servidor já conta hoje. Requisições recusadas antes de chamar a OpenAI não contam.
- **O limite escolhido é o que vale de fato.** O teto de custo diário por pessoa (`VOICE_USER_DAILY_MICRO_USD`) hoje limitaria ~25 usos por dia; por isso, em `daily` o teto de custo da pessoa acompanha o plano (`quota × VOICE_NLU_RESERVE_MICRO_USD`); em `total` e `unlimited` não há teto diário por pessoa.
- **"Ilimitado" não é "sem freio":** os tetos **globais** (`VOICE_GLOBAL_DAILY_LIMIT` e `VOICE_GLOBAL_DAILY_MICRO_USD`) e as rajadas por pessoa e por IP continuam valendo. Eles são a proteção final contra gasto inesperado na sua conta da OpenAI.
- Códigos antigos (`VOICE_TOKENS_JSON`) mantêm o limite atual (`VOICE_USER_DAILY_LIMIT`), sem alteração.

### 5.2 Variáveis novas

- `ADMIN_TOKEN_HASH` (**secret**): SHA-256 em hex da senha de admin. Ausente = rotas de admin respondem 503.
- `VOICE_DEVICES_MAX` (var, padrão `2`): PCs por código novo. String de inteiro positivo, validada como as demais.
- `VOICE_ADMIN_BURST_LIMIT` (var, padrão `10`): tentativas por minuto por IP nas rotas de admin.

### 5.3 `config()`

`VOICE_TOKENS_JSON` passa a ser **opcional**: ausente vale `{}`. Se presente, a validação atual continua igual. O gate `VOICE_AI_ENABLED` não muda.

### 5.4 Autenticação das rotas de usuário (dois passos)

1. Formato `Bearer` válido, senão 401.
2. Hash na lista fixa `VOICE_TOKENS_JSON`: vale, **sem** amarração a PC (códigos antigos, comportamento atual preservado).
3. Senão, a consulta passa para o Durable Object: procura em `tokens` com `revoked IS NULL`. Não achou: 401.
4. Código novo exige o cabeçalho `X-Device-ID` (UUID v4); sem ele ou inválido: 400.
5. Amarração: se o `device_id` já está em `devices` para aquele hash, atualiza `last_seen`; se não está e `COUNT(devices) < VOICE_DEVICES_MAX`, registra; senão **403 `{"error":"device_limit"}`**.
6. Plano de uso (ver 5.1.1): `expires` vencido dá **403 `{"error":"code_expired"}`**; em `total`, `used_total >= quota` dá **429 `{"error":"quota_exhausted","limit_reason":"token_total"}`**; em `daily`, o limite do dia e o teto de custo derivam de `quota`, e esgotar dá 429 com `limit_reason:"token_daily"` e `retry_after_seconds` até a virada do dia. `used_total` só aumenta quando a requisição é aceita (e volta se a OpenAI falhar antes de consumir, como a reserva atual).
7. O restante (rajadas, idempotência, tetos globais, OpenAI) fica como está, usando `subject`.

Os códigos de erro específicos (`device_limit`, `code_expired`, `quota_exhausted`) só são devolvidos **depois** de o código ser reconhecido, para não revelar a quem não tem código se ele existe.

Requisições sem token continuam respondendo 401 e **não** entram no Durable Object além do limite de rajada por IP já existente (ver 8).

### 5.5 Rotas de admin

Todas exigem HTTPS e `Authorization: Bearer <senha de admin>` (43 caracteres base64url). A comparação do hash usa comparação de tempo constante. Requisições com cabeçalho `Origin` são recusadas (uso só por app nativo). Nunca chamam a OpenAI e não consomem cotas de usuário.

| Rota | Corpo | Sucesso | Observações |
| --- | --- | --- | --- |
| `POST /admin/tokens` | `{"subject":"nome-da-pessoa","mode":"daily\|total\|unlimited","quota":50,"expires":null}` | `201 {"subject","token","mode","quota","expires","devices_max","created"}` | o servidor gera 32 bytes aleatórios (base64url, 43 chars), guarda só o hash; o `token` aparece **uma única vez**. `quota` obrigatório em `daily`/`total`, proibido em `unlimited` |
| `GET /admin/tokens` | — | `200 {"tokens":[{"subject","created","revoked","mode","quota","expires","used_total","devices","last_seen","today_requests"}]}` | `today_requests` vem do bucket `u:{subject}:{dia}` |
| `POST /admin/tokens/limit` | `{"subject":"...","mode":"...","quota":100,"expires":null}` | `200 {"updated":N}` | muda o plano de uso do código ativo **sem trocar o código**; zerar o pacote é `used_total=0` com `"reset_used":true` |
| `POST /admin/tokens/revoke` | `{"subject":"..."}` | `200 {"revoked":N}` | marca `revoked` em todos os códigos ativos do `subject`; vale na próxima requisição |

Erros: 400 corpo/`subject` inválido; 401 senha inválida; 409 já existe código ativo para o `subject` (revogue antes de gerar outro); 429 limite de tentativas; 503 admin desligado (`ADMIN_TOKEN_HASH` ausente) ou IA desligada onde aplicável. Nas rotas de admin o corpo de erro é sempre `{"error":"voice_unavailable"}`, como hoje, sem detalhes. 400 também cobre `mode`/`quota`/`expires` inconsistentes (por exemplo `quota` em `unlimited`, ou `expires` no passado).

## 6. App

### 6.1 ID da instalação

Arquivo `voice-device.id` na pasta de dados do canal (Beta e estável separados), com um UUID v4 gerado no primeiro uso. Não é segredo. Todas as chamadas do `RemoteAIClient` passam a enviar `X-Device-ID`.

### 6.2 Mensagem de erro

`chat.py`: resposta 403 com `device_limit` mostra "Este código já está em uso em outros computadores. Peça um novo ao administrador."; 403 com `code_expired` mostra "Este código expirou. Peça um novo ao administrador."; 429 com `quota_exhausted` mostra "O limite de uso deste código acabou. Peça mais ao administrador." Os 429 de limite diário e rajada seguem com o texto atual (que já informa o tempo de espera). O texto de 401 não muda.

### 6.3 Cliente de admin (módulo novo)

`admin_ia.py`, só biblioteca padrão, destino HTTPS fixo (o mesmo `ENDPOINT` do Worker), sem redirecionamentos, timeout de 15 s, sem retry. Funções: `salvar_senha`, `carregar_senha`, `limpar_senha`, `listar`, `gerar(subject)`, `revogar(subject)`.

A senha de admin é guardada com DPAPI em `admin-online.dpapi` (mesma técnica de `voice-online.dpapi`), nunca em log, estado ou UI. O arquivo entra no `.gitignore` e no validador de pacotes, como os atuais.

### 6.4 API do app (`web_api.py`)

`admin_ia_estado`, `admin_ia_salvar_senha`, `admin_ia_listar`, `admin_ia_gerar(subject, mode, quota, expires)`, `admin_ia_limite(subject, mode, quota, expires, reset_used)`, `admin_ia_revogar`. **Todas recusam quando o canal não é `beta`** (leitura de `CANAL_APP`/`canal_build.json`, a mesma fonte do botão "Publicar na versão original"). Na estável o retorno é "Indisponível neste canal".

### 6.5 Tela

Item **Admin** no menu, visível só no canal Beta (a forma exata de ler o canal na tela segue o mecanismo de `web/beta_publicacao.js`; confirmar na implementação).

- Sem senha salva: campo "Senha de administrador" e botão Salvar. Nada mais.
- Com senha salva: lista de pessoas (nome, plano, uso, criado em, PCs em uso, último uso, situação); formulário **Gerar código**: "Nome da pessoa", **"Limite de uso"** (Ilimitado / N por dia / N no total) com o campo do número, "Validade" opcional; por linha, **Alterar limite** (com "Zerar pacote" quando for `total`), **Revogar** com confirmação; "Trocar senha".
- Ao escolher **Ilimitado**, a tela avisa em uma linha: "Ilimitado ainda respeita o teto global diário do servidor."
- Na lista, o uso aparece no formato do plano: "12 de 50 hoje" (`daily`), "30 de 100 no total" (`total`) ou "47 hoje" (`unlimited`).
- O código gerado aparece **uma vez**, numa caixa com botão Copiar e o aviso "só aparece agora". Some ao fechar e não é gravado em lugar nenhum.
- Estados de erro em linguagem simples (sem senha, senha recusada, sem rede, nome já em uso).

## 7. Segurança

- A senha de admin é longa e aleatória, gerada no PC do dono; o servidor guarda só o hash.
- Rotas de admin com limite de rajada por IP, comparação em tempo constante, recusa de `Origin`, sem mensagens que distingam "rota existe" de "senha errada".
- O instalador **não contém** credenciais. A aba existir no código da estável não dá acesso: sem a senha ela não faz nada, e a API recusa fora da Beta.
- Códigos gerados nunca aparecem em log do app nem do servidor.
- Códigos antigos (`VOICE_TOKENS_JSON`) seguem sem amarração a PC; podem ser migrados depois gerando novos e revogando.

## 8. Rajada por IP antes do Durable Object

O caminho "código fora da lista fixa" passa a chegar ao Durable Object. Para não permitir que tráfego anônimo o sobrecarregue, o limite de rajada por IP existente (`IP_BURST_LIMIT`) é aplicado **antes** da consulta à tabela. Confirmar na implementação que o contador já cobre esse caminho; se não, mover a checagem.

## 9. Testes

Servidor (`node --test server/voice-worker/test_worker.mjs`, adaptador SQLite existente):

- gerar devolve token de 43 caracteres e grava só o hash; segundo gerar para o mesmo `subject` ativo dá 409; após revogar, gera de novo;
- listar não expõe token nem hash;
- código novo autentica; código revogado dá 401 na requisição seguinte;
- 3º PC recebe 403 `device_limit`; PC já registrado continua; `X-Device-ID` ausente ou inválido dá 400;
- código da lista fixa continua funcionando **sem** `X-Device-ID`;
- admin: senha errada 401, sem `ADMIN_TOKEN_HASH` 503, `Origin` presente recusado, limite de tentativas 429;
- `VOICE_TOKENS_JSON` ausente não derruba o servidor;
- limites: `daily` bloqueia no uso N+1 com `limit_reason:"token_daily"` e volta no dia seguinte; `total` bloqueia ao esgotar e volta ao aumentar o limite ou zerar; `unlimited` passa do limite padrão mas é barrado pelo teto global; `expires` vencido dá 403 `code_expired`; alterar o limite vale na requisição seguinte sem trocar o código; `quota` em `unlimited` e `mode` inválido dão 400; o teto de custo em `daily` acompanha `quota` (N maior que 25 não é cortado antes de N);
- erro de OpenAI antes de consumir devolve a unidade (`used_total` não fica adiantado).

App (Python):

- `RemoteAIClient` envia `X-Device-ID`; o arquivo de ID é criado uma vez e reaproveitado;
- `chat.py` mostra a mensagem do `device_limit`;
- `admin_ia` com `urlopen` simulado: monta as chamadas certas, não loga a senha, trata erros;
- `web_api` recusa as cinco funções fora do canal `beta`;
- validador de pacotes bloqueia `admin-online.dpapi`; `voice-device.id` não faz parte de pacote.

Tela (Node, no estilo de `test_chat_ui.cjs`): aba oculta fora da Beta; estado sem senha; código exibido uma vez.

## 10. Publicação do servidor (runbook, exige o dono)

1. Instalar o `wrangler` (Node 24) e fazer `wrangler login` na conta dona do Worker.
2. Gerar a senha de admin localmente e guardá-la num gerenciador de senhas; calcular o hash.
3. `wrangler secret put ADMIN_TOKEN_HASH` (interativo).
4. **Não substituir mais o `VOICE_TOKENS_JSON`**: os códigos novos não dependem dele, e os antigos continuam nele.
5. `wrangler deploy` (sem nova migração: mesma classe, tabelas criadas sob demanda).
6. Teste de fumaça: sem token 401; `GET /admin/tokens` com a senha 200 e lista vazia; gerar um código de teste, usar no app Beta, ver 2 PCs aceitos e o 3º recusado, revogar e ver 401.
7. Reversão: `wrangler rollback` (ou redeploy do arquivo anterior) e remover o secret `ADMIN_TOKEN_HASH`. As tabelas ficam, inofensivas.

O app só é publicado (Beta) depois de o servidor novo estar no ar, porque o app novo já envia `X-Device-ID`, que o servidor antigo simplesmente ignora. A ordem inversa também é segura.

## 11. Compatibilidade com a etapa 2 (contas)

- `subject` vira o **id de conta**: na etapa 2 ele vem do cadastro em vez de ser digitado na aba Admin, e o histórico de uso (`u:{subject}:{dia}`) continua valendo.
- A tabela `tokens` e o limite de PCs permanecem; o login emitirá códigos pelo mesmo caminho do `POST /admin/tokens` (chamado internamente, com um webhook do Kiwify, por exemplo).

## 12. Riscos e pontos a confirmar na implementação

- **Amarração ao PC não é à prova de fraude:** copiar a pasta de dados do app para outro PC copia também o ID e o código. Mitiga o uso casual, não um ataque deliberado.
- **Perda da senha de admin:** gera-se outra e troca-se o hash no secret; nenhum código de usuário é afetado.
- **Estado do servidor não verificado:** `VOICE_AI_ENABLED` no deploy atual é desconhecido (o repositório diz `"false"`, mas já houve respostas de limite diário, o que indica IA ligada). Confirmar no deploy.
- **Código do Worker é compacto** (176 linhas, trechos longos): a implementação deve extrair as funções novas para blocos legíveis e cobrir com testes antes de mexer em `authenticate()`.
- **Canal na tela:** confirmar como `web/` sabe que está na Beta antes de implementar a visibilidade.
- **Custo real por uso:** a reserva (`VOICE_NLU_RESERVE_MICRO_USD`, hoje 2000) é conservadora. Para fixar os planos comerciais, medir o custo médio real por requisição na Beta antes de definir preços.
- **Dia UTC:** o "por dia" vira às 21h de Brasília (meia-noite UTC), igual aos limites atuais. Mudar para meia-noite de Brasília exigiria mexer na chave dos buckets; fica fora desta etapa.
- **Concorrência:** o Durable Object é instância única; o volume esperado (poucas dezenas de pessoas) é compatível, mas vale registrar a contagem de requisições no teste de fumaça.
