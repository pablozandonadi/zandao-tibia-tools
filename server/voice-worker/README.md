# Gateway de voz Tibia Tudo



Worker existente: `https://tibia-tudo-voz.pablo-0af.workers.dev`.

Este diretório contém apenas o gateway; o aplicativo continua exigindo ativação local antes do upload.



## Operação



1. Use Node 24 e Wrangler 4, autenticado na conta proprietária. Na raiz deste diretório execute `wrangler deploy`. O nome já corresponde ao Worker existente. O deploy cria um único Durable Object SQLite pela migração `v1`. Confira se migrações existentes na conta não usam esse identificador antes do primeiro deploy.

2. O proprietário já cadastrou `OPENAI_API_KEY` como Worker Secret. Não leia nem copie esse valor. Se necessária a troca, use `wrangler secret put OPENAI_API_KEY` de forma interativa.

3. **Os códigos novos nascem na aba Admin da Beta** (ver "Administração de códigos" abaixo): um código diferente por pessoa, gerado pelo próprio servidor, exibido uma única vez. Entregue somente o código àquela pessoa por canal privado. Nunca empacote códigos no aplicativo.

4. `VOICE_TOKENS_JSON` fica **só para os códigos antigos**: objeto JSON `{ "hash-sha256-hex": "identificador-individual" }`, hashes de 64 caracteres hex minúsculos, identificadores com letras, números, `_` e `-` (até 80). Esses códigos continuam valendo, **sem amarração a PC**, com o limite diário de sempre. **Não substitua mais esse secret** (ele não é mais necessário para códigos novos e substituí-lo derrubaria os antigos). Enquanto restar algum código antigo em uso, não mexa nesse secret (os antigos continuam valendo). Quando não restar nenhum, **apague** o secret com `wrangler secret delete VOICE_TOKENS_JSON`; nunca grave `{}` nele (objeto vazio é recusado e todas as rotas de usuário passam a responder 503). O nome de um código antigo não pode ser usado num código novo (gerar responde 409).

5. Preencha `[vars]` no `wrangler.toml` com os valores aprovados abaixo, mantendo `VOICE_AI_ENABLED = "false"` enquanto testa. São todos strings de inteiros positivos, exceto o modelo. Ausência/valor inválido falha fechado com 503.

6. Somente depois de confirmar modelo, preços, acesso e orçamento, altere `VOICE_AI_ENABLED` para `"true"` e implante. Com o gate `"true"`, `POST /interpret` sem token deve responder 401; com gate OFF, as rotas de usuário respondem 503 antes de olhar o token. Nunca envie credenciais pelo browser/URL. Tokens individuais são enviados pelo cliente apenas em `Authorization: Bearer ...`, via HTTPS.



## Administração de códigos

Os códigos novos ficam no SQLite do Durable Object (tabelas `tokens` e `devices`, criadas sob demanda, sem nova migração). O servidor guarda só o hash; o código aparece uma única vez ao ser gerado.

**Senha de admin.** Gere a senha e o hash com o `node -e` abaixo, num terminal privado e sem gravação de sessão. Guarde a senha num gerenciador de senhas e cadastre só o hash: `wrangler secret put ADMIN_TOKEN_HASH` (interativo). Sem esse secret, as rotas `/admin/*` respondem 503.

```
node -e "const c=require('node:crypto'); const t=c.randomBytes(32).toString('base64url'); console.log('SENHA PRIVADA:',t);console.log('HASH:',c.createHash('sha256').update(t).digest('hex'))"
```

**Variáveis.** `VOICE_DEVICES_MAX` e `VOICE_ADMIN_BURST_LIMIT` ficam em `[vars]` no `wrangler.toml`, como strings de inteiro positivo. `VOICE_DEVICES_MAX` inválido dá 503 nas rotas de usuário (ao gerar, o admin mostra `devices_max: 2` sem avisar); `VOICE_ADMIN_BURST_LIMIT` inválido dá 503 nas rotas de admin.

| Variável | Padrão | Significado |
| --- | --- | --- |
| `ADMIN_TOKEN_HASH` (secret) | ausente = admin desligado | SHA-256 hex (64 caracteres) da senha de admin |
| `VOICE_DEVICES_MAX` | `2` | PCs por código novo |
| `VOICE_ADMIN_BURST_LIMIT` | `10` | tentativas por minuto, por IP, nas rotas de admin |

**Rotas de admin.** Todas exigem HTTPS e `Authorization: Bearer <senha de admin>` (43 caracteres base64url). Nunca chamam a OpenAI. Corpos JSON até 4096 bytes. A checagem acontece em duas etapas:

1. **No próprio Worker, antes do Durable Object** (sem tocar no banco): HTTP sem TLS ou cabeçalho `Origin` presente (uso só por app nativo) dão 403; admin desligado (`ADMIN_TOKEN_HASH` ausente ou inválido) dá 503; `Authorization` ausente ou fora do formato `Bearer` + 43 caracteres dá 401.
2. **No Durable Object**: primeiro o limite de tentativas por IP (`VOICE_ADMIN_BURST_LIMIT`, 429), depois a comparação do hash da senha em tempo constante (401 se errada). Uma senha errada bem formada conta para o limite de tentativas.

| Rota | Corpo | Sucesso |
| --- | --- | --- |
| `POST /admin/tokens` | `{"subject","mode","quota","expires"}` | `201 {subject,token,mode,quota,expires,devices_max,created}` |
| `GET /admin/tokens` | sem corpo | `200 {tokens:[{subject,created,revoked,mode,quota,expires,used_total,devices,last_seen,today_requests}]}` |
| `POST /admin/tokens/limit` | `{"subject","mode","quota","expires","reset_used"?}` | `200 {updated:N}` (muda o plano sem trocar o código; `mode` é obrigatório e `quota` segue as regras do modo; **omitir `expires` mantém a validade atual, `expires: null` a remove**, um inteiro a substitui; `reset_used:true` zera `used_total`) |
| `POST /admin/tokens/revoke` | `{"subject"}` | `200 {revoked:N}` (vale na próxima requisição) |

`subject` segue `^[a-zA-Z0-9_-]{1,80}$`. Erros de admin: 400 corpo/plano inválido (inclui `quota` em `unlimited` ou `expires` no passado), 401 senha ausente, malformada ou errada, 403 `Origin` presente ou HTTP sem TLS, 404 em `/admin/tokens/revoke` e `/admin/tokens/limit` quando o `subject` não tem código ativo, e também em rota desconhecida (só depois de a senha ser aceita), 409 já existe código ativo para o `subject` (revogue antes) ou o `subject` é de um código antigo, 413 corpo acima de 4096 bytes, 429 limite de tentativas, 503 admin desligado ou `VOICE_ADMIN_BURST_LIMIT` inválido. O corpo de erro é sempre `{"error":"voice_unavailable"}`, sem detalhes.

**Planos de uso** (`mode`; uso = uma requisição paga em `/transcribe`, `/interpret` ou `/chat`):

| `mode` | `quota` | Significado |
| --- | --- | --- |
| `daily` | inteiro >= 1 | N usos por dia UTC; o teto de custo da pessoa acompanha o plano |
| `total` | inteiro >= 1 | pacote de N usos no total (`used_total`); esgotado, para até o admin aumentar |
| `unlimited` | proibido (`null`) | sem limite próprio; os tetos globais e as rajadas por pessoa/IP continuam valendo |

`expires` (opcional) é um instante no futuro em milissegundos desde 1970 (epoch ms, como `Date.now()`), não uma duração; depois dele o código para em qualquer modo. `used_total` não volta se a OpenAI falhar depois da reserva; repetir o mesmo `X-Request-ID` (409) não conta duas vezes.

**Amarração a PC.** Código novo exige o cabeçalho `X-Device-ID` (UUID v4); ausente ou inválido, 400. Cada código aceita até `VOICE_DEVICES_MAX` PCs; o seguinte recebe 403. Códigos antigos de `VOICE_TOKENS_JSON` não usam `X-Device-ID`.

**Erros novos para o usuário** (só depois de o código ser reconhecido):

- `403 {"error":"device_limit"}`: PC além do limite.
- `403 {"error":"code_expired"}`: `expires` vencido.
- `429 {"error":"quota_exhausted","limit_reason":"token_total"}`: pacote `total` esgotado. No plano `daily`, esgotar dá 429 com `limit_reason:"token_daily"` e `retry_after_seconds` até a virada do dia UTC.

### Roteiro de deploy (exige o dono)

1. Instalar o `wrangler` (Node 24) e fazer `wrangler login` na conta dona do Worker.
2. Gerar a senha de admin localmente (comando acima), num terminal privado e sem gravação de sessão, guardá-la num gerenciador de senhas e calcular o hash.
3. `wrangler secret put ADMIN_TOKEN_HASH` (interativo).
4. **Não substituir mais o `VOICE_TOKENS_JSON`**: os códigos novos não dependem dele e os antigos continuam nele.
5. `wrangler deploy` (sem nova migração: mesma classe, tabelas criadas sob demanda).
6. Teste de fumaça, com `curl` (o app Beta com a aba Admin só sai depois do servidor; ou instale a Beta localmente antes). As rotas `/admin/*` não dependem do gate, então os passos de admin funcionam com `VOICE_AI_ENABLED = "false"`:
   - `GET /admin/tokens` sem `Authorization`: 401. Com `Authorization: Bearer <senha>`: 200 e lista vazia.
   - `POST /admin/tokens` com a senha e corpo `{"subject":"teste-fumaca","mode":"total","quota":5}`: 201 com o `token` (só aparece agora).
   - O teste de PCs usa uma rota de usuário, então exige o gate `"true"` e todas as `[vars]` preenchidas. Faça 3 chamadas `POST /interpret` com `Authorization: Bearer <token>`, `Content-Type: application/json`, `X-Request-ID` (UUID v4 novo a cada chamada), corpo `{"request_id":"<o mesmo UUID>","text":"timer de 1 minuto"}` e um `X-Device-ID` (UUID v4) diferente em cada uma. As duas primeiras dão 200 (cada uma é uma chamada paga, mínima); a 3ª dá 403 `device_limit` sem chamar a OpenAI. Com o gate ligado, `POST /interpret` sem token dá 401.
   - `POST /admin/tokens/revoke` com `{"subject":"teste-fumaca"}`: 200; a próxima chamada com o token dá 401.
7. Reversão: `wrangler rollback` (ou redeploy do arquivo anterior) e `wrangler secret delete ADMIN_TOKEN_HASH`. As tabelas ficam, inofensivas. Depois do rollback, os códigos novos recebem 401 do Worker antigo, que só conhece `VOICE_TOKENS_JSON`.

O app só é publicado (Beta) depois de o servidor novo estar no ar: o app novo já envia `X-Device-ID`, que o servidor antigo ignora. A ordem inversa também é segura.

## Configuração obrigatória



| Variável | Significado |

| --- | --- |

| `VOICE_NLU_MODEL` | `gpt-5-nano`, único modelo financeiro aprovado neste lote; trocar exige revisar preços e tetos |

| `VOICE_NLU_MAX_OUTPUT_TOKENS` | Teto de saída, inteiro 1..2048 |

| `VOICE_NLU_RESERVE_MICRO_USD` | Reserva conservadora por interpretação, em milionésimos de dólar |

| `VOICE_USER_DAILY_LIMIT` | Máximo diário UTC de requisições pagas por pessoa, somando STT e NLU |

| `VOICE_GLOBAL_DAILY_LIMIT` | Máximo diário UTC agregado |

| `VOICE_USER_BURST_LIMIT` | Máximo por pessoa em janela fixa de um minuto |

| `VOICE_IP_BURST_LIMIT` | Máximo por IP em janela fixa de um minuto; IP não substitui identidade |

| `VOICE_USER_DAILY_MICRO_USD` | Orçamento diário por pessoa |

| `VOICE_GLOBAL_DAILY_MICRO_USD` | Orçamento diário agregado |



Configuração aprovada: global **US$0,20/dia** (200000 microUSD), individual **US$0,05/dia** (50000), 100 pedidos/pessoa/dia, 1000 globais/dia, burst 10/pessoa/min e 60/IP/min. Um pedido inválido autenticado também consome burst, antes da leitura do corpo. Quota diária/custo só são reservados depois da validação.



STT reserva **30000 microUSD (US$0,03)** por chamada, antes de falar com a OpenAI: teto conservador de 16000 tokens de entrada × US$1,25/M + 2000 tokens de saída × US$5/M. A referência US$0,003/min é uma **estimativa**, não um teto. Em resposta válida com `usage.type="tokens"`, `input_tokens` inteiro 0..16000 e `output_tokens` inteiro 0..2000, liquida o custo `ceil(input_tokens * 1.25 + output_tokens * 5)` microUSD e devolve somente a diferença comprovadamente não gasta. Liquidação é atômica e só ocorre uma vez, nos buckets do dia UTC original; counts não diminuem. Sem usage válido, erro ou timeout, mantém os US$0,03 reservados. Por isso chamadas sem usage podem esgotar rapidamente o limite individual.



NLU usa `gpt-5-nano`, raciocínio `minimal`, máximo 2048 tokens de saída (incluindo raciocínio), reserva mínima 2000 microUSD (US$0,002). O JSON completo enviado, incluindo instruções e esquema, não pode ultrapassar 12000 bytes UTF-8. Estimativa conservadora: até 12000 tokens de entrada + 1024 de margem, × US$0,05/M, mais 2048 × US$0,40/M = US$0,0014704; inferior à reserva. Outros modelos ou teto de saída maior falham fechado. Este teto depende dos preços e limites oficiais conferidos em 16/10/2026; revisar se mudarem. Nenhum controle cobre gastos feitos por fora do gateway; configure também os controles disponíveis na conta OpenAI.



Fontes oficiais: [mini-transcribe](https://developers.openai.com/api/docs/models/gpt-4o-mini-transcribe), [transcrições e usage](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create), [preços](https://developers.openai.com/api/docs/pricing), [descontinuações](https://developers.openai.com/api/docs/deprecations). O snapshot `gpt-5-nano-2025-08-07` tem desligamento anunciado para **11/12/2026**; validar a migração do modelo antes dessa data, sem troca silenciosa no cliente.





## Contrato



- `POST /transcribe`: `Content-Type: audio/wav`, `X-Request-ID: UUIDv4`, corpo WAV RIFF/PCM mono 16 kHz, 16 bits little endian. Máximo 15 s e 512 KiB. Não aceita WAV vazio, truncado, formato diferente ou silêncio digital. Resposta `{request_id,text}`, texto não vazio até 500 caracteres. A transcrição usa endpoint e modelo fixos `gpt-4o-mini-transcribe`, idioma `pt`.

- `POST /interpret`: `Content-Type: application/json`, mesmo header UUIDv4, corpo exato `{request_id,text}`, texto não vazio até 500 caracteres. Retorna `{request_id,intent}`. Intent contém exatamente `action`, `parameters`, `needs_clarification`, `clarification`; o último é string curta quando precisa esclarecer, caso contrário null. Catálogo fechado: `create_timer {seconds:1..10800}`, `cancel_last_timer {}`, `cancel_timer {timer_id}`, `query_timer {timer_id}`, `shared {level:1..100000 ou null}`, `unknown {}`. IDs são alfanuméricos, `_` ou `-`, até 80 caracteres. O cliente revalida e verifica o estado local antes de executar.

- Cada UUID/pessoa/rota só pode alcançar a OpenAI uma vez, por pelo menos 48 h. Toda repetição recebe 409, inclusive após falha/timeout. Payload alterado também recebe 409. Não repetir automaticamente com UUID novo: o primeiro pedido pode ter sido cobrado. STT e NLU podem usar o mesmo UUID porque são rotas diferentes.

- Status: 400 formato, 401 credencial, 403 TLS, 413 corpo grande, 409 repetição, 429 limite/orçamento, 502 provedor inválido, 503 gate/configuração/infraestrutura, 504 timeout (15 s). Erros do provedor são sanitizados.



## Dados e limites



Sem logs de áudio, texto ou segredos; observabilidade está desabilitada. O Durable Object armazena apenas identidade, UUID, rota, hash do payload, estado, tempo, duração e custo reservado, além de buckets de quota e hash do IP. Não grava resposta/transcrição; reservas de uso desconhecido nunca são devolvidas; somente STT com contagem de tokens válida é liquidado. Limpeza limitada a 100 registros de cada tabela por pedido; metadados antigos podem permanecer mais tempo em tráfego baixo. Isso não limpa a memória operacional do provedor: conferir a política contratual OpenAI. Responses usa `store:false`.



Um singleton fornece atomicidade global e pode limitar throughput; adequado ao grupo inicial de amigos. Workers/DO Free têm limites próprios de CPU/armazenamento/requests; os testes Node não comprovam consumo de CPU nem compatibilidade do deploy real. O filtro de silêncio detecta somente zeros digitais, não classifica ruído. Não captura microfone nem relaxa wake local.



## Testes locais



Na raiz do repositório: `node --test server/voice-worker/test_worker.mjs` com Node 24. O adaptador de teste executa o SQL real em `node:sqlite`, inclusive `BEGIN/COMMIT/ROLLBACK`; somente a OpenAI é substituída. Sem dependências de runtime, instalação npm ou tráfego externo.



## Aplicativo



Em Voz → Reconhecimento online, informe o código de acesso individual e marque Ativar. Online vem desligado por padrão; o microfone/wake local continua iniciando como antes. O código é salvo com Windows DPAPI CurrentUser em `voice-online.dpapi`, nas pastas de dados separadas Beta/estável. `voice-online.json` guarda somente a opção enabled. Nenhum token sai em estado/UI/logs; o campo de senha é limpo após salvar. DPAPI inválido ou acesso ausente preservam o modo local. Esses arquivos e temporários são ignorados pelo Git e bloqueados pelo validador de pacotes.



O cliente Python usa somente stdlib, destino HTTPS fixo, timeout 15 s, sem redirecionamentos ou retries. Somente um segmento autorizado é enviado: comando após wake separado/clique, ou mesma frase com os três timestamps Vosk válidos, cortando o prefixo da ativação. Falta de alinhamento mantém o parser local e não envia áudio. Silêncio, Piper, pausa, overflow e teto da captura não sobem para o servidor. STT tenta primeiro o dispatcher local; somente UNKNOWN pede interpretação Nano. O cliente revalida o esquema e exige IDs de timers ainda ativos; shared usa a função existente. Pausa ou troca de configuração durante a requisição invalidam a resposta antes da execução. Falha online permite somente fallback determinístico local, sem retry automático.



## Validação real de 16/10/2026



A coordenação confirmou deploy Cloudflare, autenticação real (401 sem acesso/inválido e400 com payload inválido) e identificou a causa das chamadas reais502: OpenAI respondeu **429 / insufficient_quota**. Deploy diagnóstico `08a268d0` confirmou a conta sem quota/créditos. Não foi comprovada transcrição real nem interpretação Nano; o serviço fica OFF até regularizar e repetir a validação, sem microfone real nesta etapa. Testes locais finais:659 Python GREEN,22 gateway Node GREEN e NodeUI GREEN. Não confundir aprovação da infraestrutura/autenticação com benchmark de voz ou disponibilidade da conta.



Diagnóstico autenticado de502 pode incluir `provider_status` e `provider_code` somente da allowlist `invalid_api_key`, `insufficient_quota`, `model_not_found`, `rate_limit_exceeded`, `invalid_json_schema`, `invalid_request_error`. Falha de transporte recebe código fixo `provider_transport`. Nenhuma mensagem, parâmetro, chave ou corpo do provedor é devolvido/logado; sem autenticação não há diagnóstico upstream. O cliente ignora o corpo de erro e mostra falha genérica. Seu User-Agent próprio é `TibiaTudo/1.0` porque a borda Cloudflare recusou o padrão urllib no teste real.



### Crédito regularizado e nova rodada — 16/10/2026



O proprietário adicionou créditos. A coordenação confirmou STT real com Piper sintético em três casos: timer de20s, dois minutos120s e um minuto e meio90s; auth401/401/400 e replay da mesmaUUID em maiúsculas409 passaram. Isso não é benchmark de microfone. Nano ainda recebeu502 após HTTP200, compatível com saída incompleta no teto anterior512, sem validação real de intenção concluída. O teto agora é2048 e reserva2000microUSD; `status="incomplete"` recebe502 com código fixo `output_incomplete`, sem devolver reasoning nem conteúdo parcial e sem liberar reserva. A coordenação fará uma interpretação real adicional; não repetir STT já validado. Limite individual versionado permanece50000microUSD, global200000 e gate OFF no arquivo; overrides de teste são operacionais e temporários.



O corpo JSON do provedor NLU é limitado a 256 KiB (era 32 KiB; a resposta real do `gpt-5-nano` passou de 32 KiB e o chat falhava com `provider_response_too_large`, o que os testes com respostas simuladas pequenas não mostraram): comporta o eco do schema/instruções (pedido até 12000 bytes), o raciocínio, saída até 2048 tokens e metadados. Somente a intenção validada retorna ao cliente; limite de resposta do cliente e do provedor STT continua 8 KiB. Excesso NLU recebe diagnóstico fixo `provider_response_too_large`, sem conteúdo.


### Cinco módulos e contrato de interpretação — 16/10/2026

`voice/domain_actions.json` é o contrato tipado único importado pelo Worker no build e pelo cliente Python como recurso empacotado. A saída do modelo tem ação fechada e parâmetros revalidados contra a ação correspondente nos dois lados; correlação adicional é validada localmente, mesmo que o JSON Schema externo aceite união de formatos. Nenhum cálculo de Shared, stamina, cooldown, preço ou progresso é feito pelo modelo. `boss.catalog.import` e atualização de perfil não são ações NLU. Boosted recebido por NLU exige confirmação manual de elegibilidade do Archfoe do dia.

O teste envia uma requisição NLU completa com o contrato e 500 caracteres de texto e verifica até 12000 bytes UTF-8. Mantidos saída máxima 2048 tokens, raciocínio minimal e reserva 2000 microUSD: 13024 tokens conservadores de entrada × US$0,05/M + 2048 × US$0,40/M = US$0,0014704 < US$0,002. O teto global aprovado é US$0,20/dia. Nenhuma chave OpenAI vai para cliente, pacote ou logs. Resposta provider permanece limitada a32KiB; resposta pública permanece limitada pelo cliente a8KiB. Validar esse contrato novo em deploy real fica com a coordenação.

Status operacional posterior às notas históricas: créditos regularizados; coordenação confirmou STT3/3 com Piper sintético, autenticação401/401/400, replay409 e Nano legado HTTP200/intenção timer90 validada após correção32KiB (deploy e0c2436e-e124-4a78-a2d4-e6403c1bf199). Isso não comprova100gravações reais nem o novo catálogo5domínios em produção. Override individual100000microUSD foi temporário de teste; fonte versionada50000, global200000 e gateOFF permanecem sob controle da coordenação.

Fallback temporal: todos os campos de timestamp do NLU aceitam somente null. Referências de data no texto, correção de horário, projeção e cálculo reverso retornam esclarecimento em Worker e cliente antes de executar; o modelo não pode inventar data atual ou meia-noite. Operações com padrão agora (ex.: preço observado sem data) recebem o relógio local do domínio, nunca uma data gerada pelo modelo. Parser determinístico e formulários continuam tratando datas explícitas e relativas. Testes reproduziram a observação Market com timestamp inventado e confirmaram rejeição nos dois lados.

No teste real da coordenação, a data inventada do Market foi identificada antes de chamar o Store: nenhum preço ou outro dado de domínio foi gravado por essa interpretação. A correção usa timestamps null, cálculo local para o padrão agora e esclarecimento para horários pelo fallback.

Relatório final de integração dos cinco módulos (16/10/2026): revisão independente encerrada sem pendências.
Deploy confirmado pela coordenação: `3a41a51d-3500-40aa-aa23-cfef8eeeaa10`.
A mesma frase Market retornou `market.price.add`, preço36500, oferta`sell` e `observed_at:null`; intenção validada, sem gravar dados de domínio.
Guard temporal cobre timestamps inventados e expressões relativas; parser local/UI tratam horários ou o fallback pede esclarecimento.
Evidências da coordenação:691Python completos antes do guard,65focused,31Node e focused final5cliente/4Worker verdes; nenhum benchmark de microfone real.
Timers Gerais,SharedXP,BossTracker/Bosstiary,Stamina eMarket local estão integrados; publicação da Beta final e conferência dos artefatos ficam com a coordenação.


### Vocabulário contextual na transcrição (Entrega 1)

`X-Vocabulary` contém JSON UTF-8 em base64url sem padding: até 40 termos de até 40 caracteres Unicode, só letras, números, espaço, apóstrofo, ponto e hífen. Cabeçalho inválido é ignorado; não impede transcrição. Termos válidos viram um prompt de nomes, não instruções, e participam do hash da requisição. O limite de 9000 caracteres do cabeçalho comporta o pior caso UTF-8; o prompt tem menos de 8000 bytes adicionais, usados conservadoramente como até 8000 tokens extras de entrada.

Com prompt, STT reserva **40000 microUSD (US$0,04)**: envelope existente de 16000 tokens de entrada + 8000 de margem para o vocabulário, × US$1,25/M, mais 2000 tokens de saída × US$5/M. Sem prompt, mantém os 30000 microUSD. O áudio continua limitado a 15 s; esta margem depende dos preços/modelo documentados acima, não é promessa de limite do provedor. `usage` válido liquida pela mesma fórmula existente; com prompt aceita até 24000 tokens de entrada. Ausência de usage, erro, timeout ou uso acima do envelope conservam a reserva inteira. **Os tetos diários continuam US$0,20 global e US$0,05 individual**; a reserva maior pode reduzir o número de chamadas disponíveis. Modelos, limites e flags não mudam.

O cliente prioriza bosses usados recentemente (até uma hora), depois bosses com progresso no personagem capturado e os termos fixos. Essa memória permanece apenas no processo e é descartada ao trocar de personagem/mundo; não armazena áudio ou falas. A linha “Entendi” mostra a ação reconhecida em linguagem humana, sem executar a ação novamente.


### Chat de texto (`/chat`)

`POST /chat` (`Content-Type: application/json`, `X-Request-ID: UUIDv4`) usa a mesma autenticação, quotas, reserva/liquidação (`VOICE_NLU_RESERVE_MICRO_USD`), modelo, `reasoning minimal`, `store:false`, teto de saída e tratamento de erros do `/interpret`; cada UUID só chega à OpenAI uma vez (409 na repetição). Corpo exato `{request_id,messages}`, até 8192 bytes (maior recebe 413). `messages` tem de 1 a 6 itens `{role,text}`: `role` é `user` ou `assistant`, `text` é string não vazia (após trim) até 500 caracteres, e o último item é `user`. Qualquer outra forma recebe 400, sem reserva e sem chamar a OpenAI.

As mensagens vão como `input` do Responses API (nunca dentro das instruções). As instruções são o texto do chat (só Tibia e as ferramentas do Tibia Tudo; outro assunto vira `out_of_scope`) seguido do glossário do `/interpret`; a saída é JSON estrito `{kind,text,intent}`. O corpo enviado à OpenAI não pode passar de **16000 bytes** (o `/interpret` continua com 12000). A checagem ocorre **antes da reserva**: um 503 por tamanho não consome orçamento nem o UUID. Estimativa conservadora: 17024 tokens de entrada × US$0,05/M + 2048 × US$0,40/M = US$0,0016704, abaixo da reserva de US$0,002. A resposta do provedor continua limitada a 256 KiB.

Resposta `{request_id,kind,text,intent}`:

- `reply`: `text` não vazio até 1800 unidades UTF-16 e `intent` null.
- `action`: `intent` válido pelas mesmas regras do `/interpret`, inclusive o guard temporal, aplicado ao texto de todas as mensagens do jogador (uma data dita num turno anterior vale para o `sim` seguinte); `text` null ou string até 600 unidades UTF-16.
- `out_of_scope`: `text` e `intent` null.

Saída do modelo fora desse contrato, ou `status:"incomplete"`, recebe 502. O limite de reply permite tutoriais organizados; perguntas simples continuam breves. A resposta pública UTF-8 permanece dentro dos 8 KiB lidos pelo cliente. O cliente (`RemoteAIClient.chat`) revalida o corpo e a resposta com o mesmo contrato. Esta rota ainda não foi implantada nem validada contra a OpenAI real.


### Parte C: contexto e tamanho real

O limite de mensagem é contado em unidades UTF-16 (500, inclusive emojis), igual ao Worker e ao maxlength do campo; respostas no histórico são truncadas sem dividir pares de surrogate. Só a última fala pode autorizar uma ação; o histórico é contexto e nunca autoriza repetir uma ação antiga. O guard temporal permanece conservador sobre todas as falas originais.

No `/chat`, o JSON completo enviado ao provedor é medido depois de escapar o texto. Quando passa de 16000 bytes, o Worker remove as mensagens mais antigas do input até caber, preservando a última fala. Isso ocorre antes da reserva. Hash e replay continuam sobre a requisição original; quotas, modelo e reservas não foram alterados. Se nem a última fala couber, mantém a falha 503 sem reserva. A conversa não é gravada em arquivo pelo aplicativo e o pedido usa store:false; isso não substitui a política de retenção da OpenAI.

## Escopo e proteção do chat

O `/chat` só trata de Tibia e contas do jogo; outros assuntos voltam como `out_of_scope`. Cada pedido leva um segredo interno aleatório: se a resposta o contiver, vira `out_of_scope`. Links (`http(s)://`, `www.`) são removidos da resposta. Conversão gold→reais é local no app (`calculadora_gold.py`, variáveis em `conversao-tc.json`).

### Conversa direta sobre quests

O chat assume Tibia oficial, usa o assunto já esclarecido no histórico e só pergunta por um dado essencial. Quando houver informação confiável, responde com requisitos, itens, primeiro local/NPC, palavras a dizer e próximos passos. Informação incerta deve ser identificada; a rota não possui navegação e não pode prometer pesquisas. O modelo, o teto de 2048 tokens, as cotas, a reserva e os limites do histórico permanecem iguais.

Os testes usam respostas e transporte simulados: verificam instruções, contexto e limites, sem comprovar a qualidade factual de uma resposta real da IA nem consumir créditos.
