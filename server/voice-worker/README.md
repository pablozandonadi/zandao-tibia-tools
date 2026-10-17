# Gateway de voz Tibia Tudo



Worker existente: `https://tibia-tudo-voz.pablo-0af.workers.dev`.

Este diretório contém apenas o gateway; o aplicativo continua exigindo ativação local antes do upload.



## Operação



1. Use Node 24 e Wrangler 4, autenticado na conta proprietária. Na raiz deste diretório execute `wrangler deploy`. O nome já corresponde ao Worker existente. O deploy cria um único Durable Object SQLite pela migração `v1`. Confira se migrações existentes na conta não usam esse identificador antes do primeiro deploy.

2. O proprietário já cadastrou `OPENAI_API_KEY` como Worker Secret. Não leia nem copie esse valor. Se necessária a troca, use `wrangler secret put OPENAI_API_KEY` de forma interativa.

3. Gere **um token diferente por pessoa**: `node -e "const c=require('node:crypto'); const t=c.randomBytes(32).toString('base64url'); console.log('TOKEN PRIVADO:',t);console.log('HASH:',c.createHash('sha256').update(t).digest('hex'))"`. Faça isso num terminal privado, sem gravação de sessão. Entregue somente o token àquela pessoa por canal privado. Nunca empacote tokens no aplicativo.

4. Cadastre `VOICE_TOKENS_JSON` por `wrangler secret put VOICE_TOKENS_JSON`: objeto JSON `{ "hash-sha256-hex": "identificador-individual" }`. Hashes são 64 caracteres hex minúsculos; identificadores aceitam letras, números, `_` e `-`, até 80 caracteres. Para revogar, remova o hash e substitua o secret. Nunca reutilize um identificador entre pessoas; rotações podem manter o identificador para preservar quotas.

5. Preencha `[vars]` no `wrangler.toml` com os valores aprovados abaixo, mantendo `VOICE_AI_ENABLED = "false"` enquanto testa. São todos strings de inteiros positivos, exceto o modelo. Ausência/valor inválido falha fechado com 503.

6. Somente depois de confirmar modelo, preços, acesso e orçamento, altere `VOICE_AI_ENABLED` para `"true"` e implante. Uma requisição sem token deve responder 401; com gate OFF, 503. Nunca envie credenciais pelo browser/URL. Tokens individuais são enviados pelo cliente apenas em `Authorization: Bearer ...`, via HTTPS.



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



O corpo JSON do provedor NLU é limitado a 32 KiB: comporta o eco do schema/instruções (pedido até 12000 bytes), saída até 2048 tokens e metadados. Somente a intenção validada retorna ao cliente; limite de resposta do cliente e do provedor STT continua 8 KiB. Excesso NLU recebe diagnóstico fixo `provider_response_too_large`, sem conteúdo.


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

As mensagens vão como `input` do Responses API (nunca dentro das instruções). As instruções são o texto do chat (só Tibia e as ferramentas do Tibia Tudo; outro assunto vira `out_of_scope`) seguido do glossário do `/interpret`; a saída é JSON estrito `{kind,text,intent}`. O corpo enviado à OpenAI não pode passar de **16000 bytes** (o `/interpret` continua com 12000). A checagem ocorre **antes da reserva**: um 503 por tamanho não consome orçamento nem o UUID. Estimativa conservadora: 17024 tokens de entrada × US$0,05/M + 2048 × US$0,40/M = US$0,0016704, abaixo da reserva de US$0,002. A resposta do provedor continua limitada a 32 KiB.

Resposta `{request_id,kind,text,intent}`:

- `reply`: `text` não vazio até 600 caracteres e `intent` null.
- `action`: `intent` válido pelas mesmas regras do `/interpret`, inclusive o guard temporal, aplicado ao texto de todas as mensagens do jogador (uma data dita num turno anterior vale para o `sim` seguinte); `text` null ou string até 600 caracteres.
- `out_of_scope`: `text` e `intent` null.

Saída do modelo fora desse contrato, ou `status:"incomplete"`, recebe 502. O pior caso da resposta pública (600 + intent) fica abaixo de 4 KiB, dentro dos 8 KiB lidos pelo cliente. O cliente (`RemoteAIClient.chat`) revalida o corpo e a resposta com o mesmo contrato. Esta rota ainda não foi implantada nem validada contra a OpenAI real.
