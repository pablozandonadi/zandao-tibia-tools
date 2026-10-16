# Tibia Tudo — especificação de voz com IA

## Validação operacional — 16/10/2026

Após o proprietário adicionar créditos, o teste real passou: autenticação 401/401/400; três comandos sintéticos em português produziram timers de 20, 120 e 90 segundos; reenvio com UUID em maiúsculas retornou 409; GPT-5 Nano retornou intenção estruturada de timer de 90 segundos com HTTP 200. Worker e0c2436e-e124-4a78-a2d4-e6403c1bf199. A falha anterior insufficient_quota foi superada. Sem microfone, reprodução ou gravações pessoais; este smoke não substitui benchmark acústico com pessoas.

Nano usa até 2048 tokens e reserva conservadora de 2000 microUSD; respostas completas do provedor podem ter até 32 KiB por incluírem o esquema, enquanto a resposta ao aplicativo continua limitada a 8 KiB. Chave central somente no Worker; opt-in desligado em instalações novas. Acesso individual do proprietário configurado no perfil Beta do Windows.

Esta entrega cobre a fundação de voz. Os cinco módulos adicionais aprovados no PDF estão em uma etapa posterior da mesma tarefa e não são declarados implementados nesta versão. As notas abaixo preservam o histórico anterior.


Data: 16/10/2026. Estado: **execução autorizada; lote local implementado, aguardando revisão e validação acústica**.
Origem: `PLANO_SUPERPOWERS_TIBIA_TUDO_VOZ.md`, inventário do código e baseline da coordenação.
Decisão do proprietário: OpenAI `gpt-4o-mini-transcribe` para STT, família GPT Nano para interpretação e Piper TTS. Identificador Nano, suporte e acesso da conta continuam a validar. O proprietário autorizou executar o plano e escolheu servidor para manter segredo central fora do cliente; Cloudflare está em avaliação pela coordenação. Orçamento, autenticação operacional e acesso aos modelos ainda precisam de configuração.

## Objetivo e limites

Entender comandos naturais em português BR sem cortar a fala, preservar timers e shared e oferecer IA central sem distribuir chave ao cliente. Não renomear o assistente: ALEXIA é nome da conversa, não do produto.
Preservar UI, inicialização automática da voz local e funções atuais; com esfera animada autorizada no menu Voz; sem combate automatizado, shell ou conversa irrestrita.
Lote local implementado em `voz.py`, parser existente, `voice/audio_capture.py` e UI Voz. Integração OpenAI permanece desligada; contratos cloud abaixo continuam propostos.

## Base existente e pontos de integração

| Responsabilidade | Código confirmado | Consequência para implementação futura |
|---|---|---|
| Serviço e timers compartilhados | `voz.py`, `Servico.__init__/estado/comando/criar/cancelar` | Reutilizar lista em memória e IDs UUID; preservar cancelamento manual por ID |
| Wake, gramática, parser e Piper | `voice/spike_assistente.py`, `command_after_wake/recognition_grammar/dispatch/PiperSpeech` | Corrigir detector e parser compartilhados; não duplicar execução |
| Captura local | `voz.py`, `Servico._listen` | Vosk com gramática restrita; captura e fala em threads próprias |
| Shared | `tibia_info.py`, `faixa_shared(level)` | Delegar cálculo à função confiável; `shared_reply` reutiliza `faixa_shared`, com level explícito ou selecionado |
| Ponte desktop e UI | `web_api.py:1341`, `web/voz.js`, `web/index.html` | Preservar `voz_iniciar/parar/estado/criar/cancelar` e cards existentes |
| Dados e distribuição | `app_paths.data_dir`, `requirements-build.lock`, `docs/pipeline-beta.md` | Respeitar dados por canal e dependências fixadas |

`voz_ia.py` (Ollama) e `voz_elevenlabs.py` existem, mas não são importados pelo serviço atual. Não removê-los silenciosamente nem descrevê-los como integração OpenAI ativa.
`voz_credenciais.py` trata credencial pessoal protegida por DPAPI; não serve para distribuir chave central OpenAI. Arquivos de credenciais não foram lidos.
Não foi localizado backend proprietário, login ou infraestrutura de autenticação no inventário; a ponte pywebview não equivale a gateway público autenticado.

## Ativação e captura

- Obrigatório ouvir **HEY + TIBIA + TUDO**, nessa ordem, na mesma emissão; tolerar pronúncia acústica como “Ei Tíbia Tudo”, sem eliminar a primeira palavra.
- `TIBIA TUDO`, prefixos incompletos e menções no meio de conversa não ativam, transcrevem para nuvem, executam nem respondem. Exigir início do enunciado e evidência temporal da mesma emissão.
- Aceitar wake e comando juntos ou wake seguido de comando. Preservar áudio do comando que acompanha o wake.
- Após ação, retornar a IDLE e exigir novo wake completo. Continuidade sem novo wake aceita somente seleção de cancelamento pendente por 8 s, com testes; nunca aceitar nova ordem por essa exceção. Clique consciente na esfera abre uma sessão de comando sem wake, também por 8 s e somente com microfone pronto.
- Parâmetros do lote local para validar: pre-roll de 0,5 s, silêncio final de 0,8 s, máximo de comando de 15 s. Ajustar por benchmark, sem prometer precisão por esses números.
- Confirmação local: indicador visual de escuta, sem fala ou som sobreposto ao comando. Falar resposta somente após execução/erro confirmado; testar som de confirmação e Piper contra autoativação.
- Fluxo futuro: IDLE → WAKE_DETECTED → LISTENING → TRANSCRIBING → INTERPRETING → EXECUTING → SPEAKING → IDLE; erro, cancelamento, timeout e offline recuperáveis.
- Manter wake/captura local. Nunca enviar ambiente continuamente; enviar somente comando após ativação válida. Overflow, microfone desconectado e falha de TTS devem preservar UI e timers.

O detector anterior aceitava `TIBIA TUDO` sem `HEY`; o lote local removeu essa forma do parser e da gramática. Corrigir regex é necessário, mas não comprova reconhecimento acústico: o Vosk pode omitir a primeira palavra. A regra não pode ser relaxada para mascarar isso.
A fila local atual comporta 32 blocos de 100 ms. Overflow invalida a captura e a sessão, informa na tela e pede novo wake. TTS suspende captura e reseta o áudio em memória. Segmentação usa energia PCM fixa, não VAD calibrado; teto de 15 s descarta o segmento e aguarda silêncio para não executar fala truncada.

## Ações e validação

O modelo só propõe JSON estruturado; execução e validação permanecem locais e determinísticas.
Catálogo proposto: `create_timer(seconds)`, `cancel_last_timer`, `cancel_timer(timer_id)`, `query_timer(timer_id)` e `shared(level)`; mapear às funções existentes, sem introduzir uma segunda lista de timers.
Objeto externo: `action`, `parameters`, `needs_clarification`, `clarification`; enum fechado, parâmetros específicos por ação, campos extras rejeitados e valores nunca executados como código.
- Timer: segundos inteiros de **1 a 10.800**, preservando máximo atual de 180 minutos e aceitando 90 s; rejeitar bool, NaN, infinito, negativos e comando negado.
- Duração textual “um minuto e meio” → 90 s; “meio minuto” → 30 s. Regras triviais primeiro; IA apenas quando necessário, sem transformar ambiguidade em ação.
- Cancelar por duração somente com correspondência única. Duplicados exigem seleção por ID/card ou esclarecimento; se durações continuam iguais, não adivinhar o mais recente.
- `cancel_last_timer` exige timer ativo. Consultas sem referência única pedem esclarecimento. Resolver IDs novamente sob lock antes da ação.
- Shared usa `tibia_info.faixa_shared(level)` e valida level antes de chamar; não aceitar fórmula do modelo. Sem level explícito, usar somente personagem selecionado e level salvo válidos.
- Piper local permanece principal; respostas curtas sem vocativo obrigatório repetido são proposta, ainda não naturalização concluída.

## Gateway protegido — contrato implementado

Worker proprietário `https://tibia-tudo-voz.pablo-0af.workers.dev`, código em `server/voice-worker`. Deploy inicial OFF comunicado pela coordenação; operação com a conta real é validação separada. Nenhuma chave OpenAI no desktop, JavaScript ou pacote.
- `POST /transcribe`: raw WAV PCM mono 16 kHz/16 bits, até 15 s/512 KiB; rejeita WAV truncado, formato inválido e silêncio digital. Retorna `{request_id,text}`, texto não vazio até 500 caracteres.
- `POST /interpret`: JSON exato `{request_id,text}`, texto não vazio até 500 caracteres; retorna `{request_id,intent}`. Schema fechado e revalidado no cliente, sem ferramentas/shell/URLs.
- Ambos exigem TLS, `Authorization: Bearer <código individual>` e `X-Request-ID` UUIDv4. UUID é normalizada para minúsculas; repetição por usuário/rota retorna409 durante pelo menos48h, mesmo após timeout ou payload diferente. Sem retry automático.
- Tokens individuais têm32bytes CSPRNG; WorkerSecret guarda somente mapa SHA256→identidade. Segredo OpenAI fica só no Worker. Revogação remove hash; não há endpoint admin público. Cliente guarda código com DPAPI CurrentUser na pasta de dados do canal, online OFF por padrão, nunca retorna token no estado.
- Singleton SQLite Durable Object reserva atomicamente quota diária e custo antes do provedor. Burst usuário/IP é debitado antes de ler corpo autenticado, inclusive para inválidos. IP é hash e não substitui identidade.
- Status400/401/403/409/413/429/502/503/504, erros sanitizados. Corpo lido com teto de streaming, timeout de provedor15s, resposta máxima8KiB.
- Metadados mínimos por48h e limpeza limitada por pedido; sem áudio, texto ou respostas persistidas. Retenção OpenAI precisa ser conferida separadamente. Responses usa `store:false`; observabilidade Worker desabilitada.

## Modelos e custo — conferência documental em 16/10/2026

- STT proprietário: `gpt-4o-mini-transcribe`. US$0,003/min é estimativa, não teto. Reserva prévia30000microUSD considera16000tokens de entrada×US$1,25/M e2000saída×US$5/M; só liquida diferença comprovada por usage tokens válido, atomicamente no dia original. Sem usage, erro ou timeout mantém reserva.
- NLU proprietário `gpt-5-nano`, reasoning minimal, teto512saída e12000bytes UTF8 do JSON completo de entrada; reserva mínima1000microUSD cobre entrada12000+1024tokens de margem e512saída nos preços US$0,05/M eUS$0,40/M. Outros modelos/tetos exigem revisar o gate. Depreciação não significou indisponibilidade imediata: o snapshot `gpt-5-nano-2025-08-07` tem desligamento anunciado em11/12/2026; preparar migração antes dessa data.
- Global autorizado200000microUSD/dia (US$0,20); individual50000(US$0,05);100pedidos/pessoa/dia e1000globais/dia, bursts10/pessoa/min e60/IP/min. Gate servidor permanece OFF na configuração versionada; ativação real fica com a coordenação após verificar conta e operação.
- Custos reais, disponibilidade efetiva na conta e qualidade PT-BR não são comprovados pelos testes locais. Fontes oficiais e instruções de deploy em [README do gateway](../../../server/voice-worker/README.md).

## Revisão, validação e liberação

O [baseline](../plans/2026-10-16-tibia-tudo-voice-baseline.md) registra resultados e lacunas; 32 testes verdes atuais não provam que os requisitos novos funcionam.
Exigir testes RED de wake completo/incompleto, 90 s, negação, duplicados, payload adversarial, falha de rede e idempotência antes de alterar cada comportamento.
Medir com o mesmo corpus PT-BR e áudio consentido: corte de fala, intenção/parâmetros, ações indevidas, p50/p95, CPU/RAM e custo por 1.000 comandos; incluir jogo/TeamSpeak e TTS real. Não prometer experiência equivalente a Alexa/Siri.
Pendências: revisão final da integração, validação acústica, acesso efetivo da conta, custo/latência real e retenção operacional do provedor. Autenticação e orçamento estão implementados com valores explícitos; validação local não encerra rollout.
Após aprovação e implementação validada, seguir pipeline oficial da Beta com rollout gradual e rollback; estável depende da aprovação específica do usuário. Este lote altera o aplicativo local; publicação e revisão independente ficam com a coordenação.

### Esclarecimento de revisão — wake separado do comando

A exigência de mesma emissão aplica-se às três palavras `Hey` + `Tibia` + `Tudo`. O comando pode vir na mesma emissão (cortando o prefixo por timestamps) ou no segmento seguinte dentro da sessão autorizada de8s. Ambas as formas foram pedidas pelo proprietário. Um apontamento de revisão que proibia o segundo formato foi rejeitado pela coordenação por conflitar com a especificação. Nunca transmitir segmento ambiente anterior ao wake; um comando posterior autorizado tem seu próprio PCM.

Revisão final corrigida: negações correntes(`jamais`, `evite`, `deixe de` e variações) são bloqueadas antes de qualquer HTTP e no dispatcher; configuração invalida autorização em voo antes de DPAPI/disk e permanece offline no runtime se falhar. A comprovação é textual/mockada; não afirma que Vosk reconheça toda negação acusticamente.

## Operação real — 16/10/2026

A coordenação validou Worker/autenticação reais e recebeu502 com diagnóstico OpenAI429 `insufficient_quota` no deploy `08a268d0`. Conta sem quota/créditos: transcrição real e Nano continuam bloqueados. Manter serviço OFF até regularização; depois validar novamente acesso, qualidade, latência e custo. Não houve teste com microfone nem benchmark concluído. Infraestrutura/autenticação aprovadas não comprovam os resultados de voz.
