# Tibia Tudo — Assistente de Voz com OpenAI Implementation Plan

## Validação operacional — 16/10/2026

Após o proprietário adicionar créditos, o teste real passou: autenticação 401/401/400; três comandos sintéticos em português produziram timers de 20, 120 e 90 segundos; reenvio com UUID em maiúsculas retornou 409; GPT-5 Nano retornou intenção estruturada de timer de 90 segundos com HTTP 200. Worker e0c2436e-e124-4a78-a2d4-e6403c1bf199. A falha anterior insufficient_quota foi superada. Sem microfone, reprodução ou gravações pessoais; este smoke não substitui benchmark acústico com pessoas.

Nano usa até 2048 tokens e reserva conservadora de 2000 microUSD; respostas completas do provedor podem ter até 32 KiB por incluírem o esquema, enquanto a resposta ao aplicativo continua limitada a 8 KiB. Chave central somente no Worker; opt-in desligado em instalações novas. Acesso individual do proprietário configurado no perfil Beta do Windows.

Esta entrega cobre a fundação de voz. Os cinco módulos adicionais aprovados no PDF estão em uma etapa posterior da mesma tarefa e não são declarados implementados nesta versão. As notas abaixo preservam o histórico anterior.


> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended when available) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o assistente de voz do Tibia Tudo em uma interface de comandos naturais em português brasileiro, rápida, previsível, econômica e segura para distribuição a múltiplos usuários.

**Architecture:** Detecção local de ativação + captura/VAD local + transcrição de áudio via API OpenAI em backend protegido + interpretação por modelo de texto barato, usando esquema de ações estritamente validado + execução de funcionalidades existentes no computador do usuário + resposta curta por TTS local. Manter fallback local e preservar o comportamento atual até a validação de uma migração gradual.

**Tech Stack:** Python (aplicativo existente), JavaScript (interface existente), OpenAI API (modelos selecionados via configuração), Piper TTS (já citado no histórico), captura de microfone/VAD e autenticação/servidor seguro a confirmar no repositório, testes pytest e testes JS conforme infraestrutura encontrada.

**Spec:** `docs/superpowers/specs/2026-10-16-tibia-tudo-voice-ai.md` (criar a partir do bloco de especificação abaixo antes de executar tarefas).

## Atualização de execução — 16/10/2026

**Execução autorizada pelo proprietário: “execute o plano”.** O lote local de wake, comandos, captura e menu Voz foi implementado para revisão, sem alterar versão/build. O usuário aprovou uma esfera animada no menu Voz, escuta local automática e clique explícito que abre uma sessão de comando sem wake. Pausa manual e timers compartilhados permanecem disponíveis.

Gateway Cloudflare e cliente integrado estão preparados e testados localmente. A coordenação informou deploy inicial **OFF** do Worker `tibia-tudo-voz`; acesso efetivo à conta OpenAI, teste sintético do serviço real e ativação operacional ficam com a coordenação. Nenhum segredo OpenAI no cliente. STT: `gpt-4o-mini-transcribe`; NLU proprietário: `gpt-5-nano`, com migração a validar antes do desligamento anunciado do snapshot em 11/12/2026. Online no aplicativo é opt-in OFF, com código individual protegido por Windows DPAPI por canal. Orçamento global autorizado US$0,20/dia; limite individual US$0,05/dia, STT reserva conservadora US$0,03 e NLU US$0,001. Contratos e justificativa financeira em [server/voice-worker/README.md](server/voice-worker/README.md).

- Wake textual exige três palavras (hey/ei/hei + tibia + tudo); formas incompletas e bare `TIBIA TUDO` são rejeitadas. Após ação exige nova ativação; seleção pendente aceita somente esclarecimento por até 8 s. Clique abre uma sessão de 8 s apenas com microfone pronto.
- Captura PCM local em memória: pre-roll 0,5 s, silêncio final 0,8 s e teto 15 s. Teto/overflow rejeitam o comando; Piper não produz confirmação longa de wake. Reconhecimento acústico das três palavras **não foi comprovado**: a sonda anterior perdeu “Ei”; nunca relaxar a regra para ocultar essa limitação.
- Testes RED observados e GREEN atual registrados no [baseline](docs/superpowers/plans/2026-10-16-tibia-tudo-voice-baseline.md) e ledger. Task 1/2 continuam parciais até benchmark/hardware; integração mockada de 90 s foi adicionada.
- Gateway: 19 testes Node/SQLite real GREEN; cliente/local: suíte completa 659 testes Python GREEN no runtime do aplicativo e Node UI GREEN. Benchmark acústico, custos reais, acesso da conta e publicação continuam com a coordenação. O programador não faz commits nem publica.

**Verificação real de 16/10/2026:** infraestrutura Cloudflare e autenticação passaram; OpenAI respondeu429 `insufficient_quota` (deploy diagnóstico `08a268d0`). Integração está preparada e testada com mocks; transcrição real/Nano e qualidade estão bloqueados pela quota da conta. Serviço permanece OFF até o proprietário regularizar e a coordenação validar novamente. Tasks4/5 não estão concluídas em produção; benchmark/microfone continuam pendentes.

## Contexto e limites da evidência

- Os três `rollout-*.jsonl` fornecidos contêm fragmentos de sessões do Codex (incluindo revisões), não uma cópia completa e atualizada do repositório. Não os tratar como prova de funcionamento em produção.
- Há referências a `voice/spike_assistente.py`, `web/voz.js`, Vosk, Ollama, Piper, ElevenLabs, timers e wake phrase `Hey Tibia Tudo`. Localizar, abrir e conferir todos eles antes de qualquer modificação.
- O usuário relatou fala cortada, necessidade de falar excessivamente pausado, reconhecimento defeituoso de termos como timer/shared/level e interesse em reconhecimento próximo da experiência Alexa/Siri. Não prometer equivalência sem benchmarks locais.
- Requisitos: serviço disponível a todos os usuários sem precisar de chave OpenAI própria; comandos curtos; máxima economia; chave central jamais distribuída aos clientes; português BR; interface responsiva; manutenção de comandos e temporizadores existentes.
- O assistente **ainda não possui nome definido**; `ALEXIA` é somente o nome da conversa do Codex. Não renomear UI para ALEXIA.
- Preços e disponibilidade de modelos mudam. Conferir em `https://developers.openai.com/api/docs/pricing` e páginas oficiais de modelo no momento da implementação. Não presumir que um modelo previamente citado está disponível na conta; selecionar identificadores válidos e atuais na API. Não supor custo fixo por comando.
- Não armazenar gravações ou transcrições por padrão, salvo consentimento e finalidade explícita. Evitar incluir dados de chat privado do TeamSpeak.

## Escopo aprovado para implementação

1. Captura de voz robusta, detecção correta de começo/fim de frase e wake word local.
2. Transcrição com OpenAI `gpt-4o-mini-transcribe`, escolhida pelo proprietário; validar acesso da conta, limites e qualidade no benchmark antes de implementar.
3. Classificação estruturada de intenção com a família GPT Nano, escolhida pelo proprietário; identificador exato, ciclo de vida, suporte e disponibilidade na conta pendentes de validação, com fallback local para comandos triviais.
4. Orquestração de comandos *sem* permitir ao modelo executar ações arbitrárias.
5. Respostas faladas curtas via Piper; manter o modo de voz do projeto sem regressão.
6. Servidor intermediário proprietário, autenticação, rate limit e controle de custos por usuário.
7. Testes automatizados, testes com microfone real e distribuição gradual.

## Fora do escopo nesta fase

- Assistente conversacional irrestrito, acesso irrestrito ao sistema operacional e automação de combate no Tibia.
- Uso de API key OpenAI no código JavaScript, no executável, em variáveis de ambiente empacotadas ou em arquivos distribuídos.
- Cobrança dos usuários e gestão de planos.
- Redesenho total da UI ou reescrita integral dos módulos de timer.

## Especificação de experiência

### Fluxo normal

1. Aplicativo escuta **localmente** exclusivamente a frase de ativação **completa, de três palavras, `HEY TIBIA TUDO`**, nessa ordem. A expressão isolada `TIBIA TUDO` **NÃO ativa** o assistente, em nenhuma hipótese. Não transmitir áudio ambiente a terceiros.
2. Após detectar ativador, preservar pequena janela de áudio anterior e iniciar sessão de comando; indicar escuta na esfera **sem bloquear ou contaminar** a captura do próximo trecho.
3. Capturar o comando até silêncio final, respeitando pausas naturais. Duração máxima e cancelamento configuráveis; medir corte de início e fim.
4. Enviar somente o áudio do comando por canal TLS ao backend autenticado. O backend chama endpoint oficial de transcrição sem expor a chave.
5. Tentar resolver comandos triviais por regras locais determinísticas; para ambiguidade, pedir ao modelo texto estruturado; nunca confiar cegamente nos valores retornados.
6. Validar ação, autorização, domínio, duração de timer e estado do app. Se houver ambiguidade relevante, solicitar esclarecimento em vez de inferir.
7. Executar função já existente do aplicativo; responder por Piper somente após sucesso real (ou declarar erro).
8. Voltar ao estado de espera. Não manter streaming de áudio para nuvem continuamente.

### Regra obrigatória e não negociável de ativação (wake phrase)

- A sequência de ativação é **`HEY` + `TIBIA` + `TUDO`**, nessa ordem e na mesma emissão de voz. A palavra `HEY` é **obrigatória**, não opcional.
- Falar apenas **`TIBIA TUDO`** deve ser ignorado; isso é referência ao nome do aplicativo, **não um pedido de ativação**.
- `HEY` isolado, `TIBIA` isolado, `TUDO` isolado, `HEY TIBIA`, `HEY TUDO` e frases que apenas mencionem o nome do programa não ativam.
- É aceitável tolerar pequenas variações acústicas de pronúncia de **todas as três palavras**, mas **nunca** dispensar a detecção da primeira palavra `HEY`. Não implementar normalizações que transformem `TIBIA TUDO` em wake válido.
- Sem wake válido, não iniciar captura/transcrição da instrução, não chamar OpenAI, não executar ações, não produzir resposta de ativação.
- Depois de wake válido: aceitar tanto `HEY TIBIA TUDO, crie um timer de 30 segundos` na mesma frase quanto `HEY TIBIA TUDO` seguido por comando após aviso de escuta. Não perder o áudio subsequente ao wake.
- Após executar a ação, voltar ao modo de espera e exigir o wake completo para **nova** interação; exceções de continuidade, caso existam, precisam ser explicitamente aprovadas e testadas.
- Aplicar bloqueio de autoativação por áudio do próprio TTS e testar áudio reproduzido por Tibia/TeamSpeak.

**Testes obrigatórios (RED antes do código):**

| Áudio/frase | Resultado esperado |
|---|---|
| `HEY TIBIA TUDO` | Ativar e aguardar comando |
| `HEY TIBIA TUDO, inicia timer de 30 segundos` | Ativar e criar timer de 30 s |
| `TIBIA TUDO` | **Não ativar** |
| `TIBIA TUDO, inicia timer de 30 segundos` | **Não ativar nem criar timer** |
| `HEY TIBIA` / `HEY TUDO` / `HEY` | **Não ativar** |
| Conversa comum mencionando `TIBIA TUDO` | **Não ativar** |
| Voz do Piper pronunciando a expressão | **Não autoativar** |

### Frases alvo

- `Hey Tibia Tudo, coloca um timer de um minuto e meio` → `create_timer(seconds=90)`.
- `me avisa daqui a meio minuto` → `create_timer(seconds=30)`.
- `cancela o último timer` → `cancel_last_timer` somente com timer existente.
- `cancela o de dois minutos` → `cancel_timer` somente se houver correspondência única; caso contrário, solicitar qual.
- `quanto falta naquele timer?` → consulta local do timer referenciado, esclarecimento se ambíguo.
- `qual é a minha shared no level 450?` → usar função confiável de cálculo existente; não inventar fórmula nem dados.
- `timer` pronunciado como `time`, `shared` como `cherd`, `level` com pronúncia brasileira → casos de transcrição e interpretação para medir, não depender apenas de substituições cegas.
- Fala fora de escopo: recusar execução e informar que ainda não há comando suportado.

### Estados do assistente

`IDLE -> WAKE_DETECTED -> LISTENING -> TRANSCRIBING -> INTERPRETING -> EXECUTING -> SPEAKING -> IDLE`; com `ERROR`, `CANCELLED`, `TIMEOUT` e `OFFLINE` recuperáveis. Estados e transições registrados sem dados pessoais desnecessários.

### Contrato de interpretação (exemplo, não acoplado ao provedor)

```json
{
  "action": "create_timer",
  "parameters": {"seconds": 90},
  "needs_clarification": false,
  "clarification": null,
  "confidence_policy": "validated_by_application"
}
```

- Usar Structured Outputs / JSON Schema no endpoint escolhido, caso suportado. Caso não suportado, JSON parse + validação rigorosa e reparo limitado; jamais executar resposta em linguagem natural como código.
- `action` é enum de ações autorizadas; `parameters` requer limites (ex.: timer >0 e limite máximo existente); rejeitar campos extras.
- Não considerar pontuação numérica autodeclarada pelo LLM como confiança calibrada.

## Global Constraints

- Preservar os timers, alertas, cálculo de shared, UI e voz já existentes, confirmando escopo pelo repositório real.
- Manter português brasileiro como idioma padrão, mas aceitar nomes próprios/termos técnicos do Tibia.
- Separar claramente reconhecimento de fala (STT), interpretação (NLU), execução de comandos e síntese de fala (TTS).
- Nenhum segredo no cliente; a API OpenAI só deve ser chamada por backend confiável.
- Mínimo de dados: somente comando necessário, com política de retenção definida; não registrar áudio bruto/transcrição em logs por padrão.
- O aplicativo deve continuar utilizável com API indisponível; comandos locais essenciais devem continuar funcionando.
- Preferir instruções concisas, sem histórico extenso e saída estrutural curta para reduzir tokens.
- Não efetuar deploy nem publicar chaves sem aprovação explícita do proprietário.
- Criar testes primeiro (RED), implementação mínima (GREEN), refatorar, repetir; commits pequenos.

## Review Focus

1. Fala é cortada pela reprodução `Pode falar` ou por decisão incorreta de silêncio.
2. Wake word falsa dispara com áudio do Tibia/TeamSpeak ou com a própria resposta TTS.
3. Tempo `um minuto e meio`, negações e cancelamentos ambíguos geram ação incorreta.
4. Cliente malicioso tenta abusar de API key por proxy público ou autenticação fraca.
5. Instabilidade/latência de rede bloqueia comandos locais ou faz o UI congelar.

## Inventário a criar ANTES do primeiro commit

- [x] `git status`, branch, testes atuais e ponto de restauração (evidência no baseline de 16/10/2026).
- [x] Confirmar stack, entrypoints, requisitos e distribuição (desktop pywebview; dependências fixadas e pipeline documentados no baseline).
- [x] Achar arquivos reais por busca de voz/wake/timer/shared; caminhos confirmados na especificação, sem ler dados pessoais.
- [x] Confirmar localização das funções atuais de timer/shared, detecção de wake, captura/endpointing Vosk, TTS e frontend; VAD robusto separado ainda não implementado.
- [ ] Registrar decisões em `docs/superpowers/specs/2026-10-16-tibia-tudo-voice-ai.md`; submeter projeto antes de implementação, seguindo `superpowers:brainstorming`.
- [ ] Mapear infraestrutura de hospedagem/backend existente; se não houver backend confiável, não expor chave nem improvisar proxy aberto.
- [ ] Confirmar preço, disponibilidade, limites, suporte a structured outputs e processamento dos modelos na documentação oficial.

## Mapa proposto de componentes (CAMINHOS DEPENDEM DO INVENTÁRIO)

| Responsabilidade | Caminho de referência (criar/adaptar) |
|---|---|
| Orquestração e estados | `voice/assistant_controller.py` |
| Capture/VAD + proteção de início/fim | `voice/audio_capture.py` |
| Cliente do backend | `voice/remote_ai_client.py` |
| Motor de intents local | `voice/command_router.py` |
| Esquema e validação | `voice/command_schema.py` |
| Ponte com timers e shared existentes | `voice/actions.py` |
| Respostas faladas | adaptar módulo Piper existente |
| Integração interface | adaptar `web/voz.js` se existir |
| Endpoint backend autenticado | `server/routes/voice.py` (exemplo apenas) |
| Client OpenAI SOMENTE backend | `server/services/openai_voice.py` (exemplo apenas) |
| Configuração e orçamento | `server/services/usage_limits.py` (exemplo apenas) |
| Testes de fluxo | `tests/voice/` e `tests/server/` |

Os nomes acima são **propostos**, não afirmações de que existam. O Codex deve substituir pelos caminhos verdadeiros após examinar o repo. Nunca criar uma segunda implementação paralela às cegas.

## Chunk 1: Linha de base e diagnóstico da voz

### Task 1 — Capturar baseline reproduzível

**Parcial em 16/10/2026:** inventário, regressões e sondas registrados no baseline vinculado acima; teste novo de integração de áudio, microfone real e medidas ponta a ponta pendentes.
- [ ] Escrever teste de integração que reproduza comportamento atual de timer de 90 segundos com áudio mockado.
- [ ] Executar e documentar falha ou sucesso antes de alterar código.
- [ ] Produzir inventário de módulos, dependências, testes e efeitos colaterais.
- [ ] Registrar baseline de CPU, RAM e latências por estágio, usando medição real.
- [ ] Commit: `test(voice): capture current assistant baseline`.

### Task 2 — Corrigir captura, turn-taking e VAD
- [ ] Criar testes de áudio sintético para silêncio interno, fala contínua, fim de frase, início cortado, TTS sobreposto e microfone indisponível.
- [ ] Verificar testes falhando onde há regressões.
- [ ] Implementar pre-roll circular, política de silêncio final, tempo máximo e suspensão/echo handling do TTS durante captura.
- [ ] Validar com gravações reais consentidas e sem dados privados.
- [ ] Commit: `fix(voice): robust speech segmentation and turn taking`.

## Chunk 2: Integração OpenAI segura

### Task 3 — Backend autenticado e custeio central

**Preparado:** Worker + singleton SQLite Durable Object, tokens individuais hash-only, burst antes do corpo, quotas/reserva atômica e replay UUID canônica, gate OFF. Testes locais GREEN; implantação/acesso real pela coordenação, sem marcar a operação concluída aqui.
- [ ] Testes primeiro: sem credencial retorna 401; usuário autenticado pode enviar somente áudio com limites de tamanho/duração; limites retornam 429; segredos jamais aparecem em respostas/logs.
- [ ] Criar API intermediária em infraestrutura confiável já adotada pelo projeto; rejeitar proxy aberto.
- [ ] Aplicar autenticação, TLS, limites por usuário e por IP com precauções contra IP compartilhado, quotas de gasto e orçamento global; recusar payload excessivo.
- [ ] Gravar somente metadados mínimos (usuário pseudônimo, duração, tokens quando fornecidos, custos estimados, latência, erro).
- [ ] Commit: `feat(server): secure metered voice gateway`.

### Task 4 — STT hospedado com seleção e fallback

**Preparado:** WAV validado, cliente fixo autenticado, resample stdlib, corte do wake por timestamps Vosk, timeout sem retry e fallback local. Casos PT sintéticos/mockados GREEN; conta, qualidade/latência/custo real e benchmark de microfone ainda pendentes.
- [ ] Testes usando SDK HTTP mockado: arquivo válido, silêncio, falha 401/429/5xx, timeout, áudio vazio e sotaque PT-BR.
- [ ] Implementar transcrição em backend com `gpt-4o-mini-transcribe`, escolhido pelo proprietário, após validar conta e limites; configuração permanece no backend.
- [ ] Transcrever somente áudio após wake word, com duração limitada; não armazenar áudio por padrão.
- [ ] Permitir comparação A/B com STT local sem alterar camada seguinte.
- [ ] Commit: `feat(voice): configurable cloud transcription`.

### Task 5 — Interpretador de intenção GPT econômico

**Preparado:** GPT Nano no backend, Structured Outputs estrito, validação servidor/cliente, catálogo fechado e reserva conservadora documentada. Sem prova de acesso/qualidade/custo na conta neste lote; não considerar benchmark concluído.
- [ ] Criar casos de teste para linguagem informal, variações de tempo, termos Tibia, negações, erros de transcrição, frases adversariais e retornos malformados.
- [ ] Implementar prompt mínimo com catálogo restrito de ações + GPT Nano escolhido pelo proprietário; validar identificador, suporte e disponibilidade da conta e medir custo, qualidade e latência antes de fixar a configuração no backend.
- [ ] Resposta obrigatoriamente validada contra schema; permitir esclarecimento; não habilitar execução arbitrária.
- [ ] Medir tokens entrada/saída e erro de interpretação separadamente do erro STT.
- [ ] Commit: `feat(voice): low-cost structured intent parser`.

## Chunk 3: Integração com Tibia Tudo

### Task 6 — Router híbrido e ferramentas determinísticas

**Preparado:** STT → dispatcher local → Nano somente UNKNOWN, mesmas funções/timers/shared, IDs ativos e geração de autorização revalidados. Rede fora do lock; pausa/configuração invalidam resposta pendente. Testes PT e falhas GREEN; execução com hardware/serviço real permanece por validar.
- [ ] Testes: timers simples sem chamadas GPT; linguagem livre interpretada por GPT; shared calcula com função existente; ações inexistentes rejeitadas.
- [ ] Implementar roteador determinístico primeiro, GPT apenas para casos incertos; validar ação novamente antes de executar.
- [ ] Reaproveitar funções do app, evitar duplicação de lógica de negócio.
- [ ] Commit: `feat(voice): hybrid local and AI command routing`.

### Task 7 — Clareza e continuidade conversacional mínima
- [ ] Testes: `cancela o último`, `cancela o de dois minutos` com dois timers de mesma duração, `não, o outro`, comando sem timer existente.
- [ ] Implementar estado de diálogo local mínimo, com expiração curta e limpeza após ação; sem enviar histórico inteiro para nuvem.
- [ ] Confirmar execução antes de dizer `feito`; quando ambíguo pedir especificação.
- [ ] Commit: `feat(voice): safe contextual clarifications`.

### Task 8 — UI, Piper e feedback de latência
- [ ] Testes de estados visuais: ouvindo, processando, concluído, sem rede, cancelado, erro de microfone; regressão de timers.
- [ ] Adaptar interface existente sem redesenhar tudo; manter interrupção de TTS para novo comando apenas se seguro.
- [ ] Piper responde com frases curtas; não falar mensagens inteiras do modelo se não forem necessárias.
- [ ] Medir tempo `fim da fala -> execução -> início do TTS`.
- [ ] Commit: `feat(voice): responsive assistant voice feedback`.

## Chunk 4: Custos, qualidade e segurança

### Task 9 — Orçamento, proteção contra abuso e painel operacional
- [ ] Testar limites por usuário/hora/dia, limite global mensal, burst, contas inexistentes, duplicidade de requisição e replay.
- [ ] Implementar idempotência para evitar timers duplicados após retry; alerta de gasto e botão administrativo de desativação da IA.
- [ ] Configuração por backend: modelo STT, modelo NLU, máximo de áudio, teto de tokens de saída, timeouts e fallback.
- [ ] Expor custos estimados e métricas agregadas sem gravação desnecessária de conversas.
- [ ] Commit: `feat(server): AI usage guardrails and observability`.

### Task 10 — Benchmark de fala natural antes da migração
- [ ] Preparar pelo menos 100 enunciados representativos em PT-BR: 20 timers, 15 cancelamentos, 15 consultas, 15 shared/level, 15 variações informais, 10 sons/ruído, 10 casos ambíguos ou não suportados.
- [ ] Para ao menos parte do corpus, obter áudio real consentido com fala normal e ruído semelhante ao Tibia/TeamSpeak.
- [ ] Medir separadamente: WER/CER de STT, acerto de intenção + parâmetros, taxa de corte de fala, ações indevidas, p50/p95 de latência, custo por 1.000 comandos, CPU/RAM e erros de backend.
- [ ] Metas provisórias a validar em baseline: >=95% de intenção+parâmetros em comandos suportados e áudio limpo; **zero** execuções perigosas/sem autorização; p95 de resposta perceptível compatível com experiência responsiva. Ajustar por hardware/rede, sem falsear resultados.
- [ ] Comparar Vosk, Whisper local se viável e API OpenAI, sobre o MESMO corpus. Selecionar por qualidade real/custo.
- [ ] Commit: `test(voice): reproducible Portuguese command benchmark`.

### Task 11 — Failover e liberação controlada
- [ ] Testes: perda de internet, 401/429 OpenAI, backend indisponível, TTS falha, usuário cancela, microfone desconecta.
- [ ] Priorizar operações locais onde possível; mensagens claras de indisponibilidade para comandos dependentes da nuvem.
- [ ] Feature flag desativada por padrão; piloto controlado, rollout gradual e rollback documentado.
- [ ] Executar teste ponta a ponta real com microfone/áudio, incluindo cooldown após TTS.
- [ ] Commit: `feat(voice): safe AI rollout and offline fallback`.

## Regras para API e segurança

- Nunca colocar `OPENAI_API_KEY` no Git, no desktop, no navegador ou no pacote distribuído. Somente configuração segura do backend. Não usar somente ofuscação/DPAPI como substituto de backend para chave compartilhada.
- Usar SDK oficial atualizado; implementar timeouts, tratamento de erros, retry com backoff somente onde idempotente, limites de tamanho e MIME do áudio.
- Prompt do GPT restrito a interpretação sem acesso à internet, arquivos ou shell; conteúdo transcrito é **entrada não confiável**, nunca instrução de sistema.
- Tabela de ações permitidas explicitamente versionada; timer e shared continuam determinísticos.
- Criptografar trânsito; revisar retenção e termos dos fornecedores; limitar acesso a métricas individuais.
- Se custo oficial, disponibilidade ou capacidades dos candidatos mudarem, atualizar plano e justificar substituição antes de implementar.

## Critérios de aceite da entrega

- [ ] Assistente entende frases naturais comuns sem exigir pronúncia robótica; demonstração com áudio real.
- [ ] Wake word exige **as três palavras `HEY TIBIA TUDO`** na ordem; `TIBIA TUDO` isolado **nunca ativa**; casos positivos/negativos acima passam em testes automatizados e gravações reais.
- [ ] Wake word, detecção de fim e TTS não cortam a fala ou criam ciclo de autoativação.
- [ ] Timer 90 s, 30 s, cancelamento último/específico/ambíguo e shared testados ponta a ponta.
- [ ] Chave da OpenAI nunca sai do servidor; cliente autenticado; rate limit e orçamento ativo.
- [ ] Falha de nuvem não quebra o app ou funções locais.
- [ ] Custo estimado por 1.000 comandos e p50/p95 de tempo são medidos, não adivinhados.
- [ ] Todos os testes de regressão e novos testes passam; nenhuma funcionalidade atual removida silenciosamente.
- [ ] Guia operacional com configuração segura, deploy, rollback, logs e custos.

## Execução via Superpowers quando os créditos retornarem

1. Abra o repositório original no Codex e carregue este documento.
2. Ative `superpowers:using-superpowers` e `superpowers:brainstorming`, confirme o desenho e crie a especificação mencionada acima. Não alterar código até validar desenho.
3. Use `superpowers:using-git-worktrees` para trabalhar em branch isolada, se o projeto estiver versionado.
4. Use `superpowers:writing-plans` para ajustar estes passos a **caminhos exatos encontrados no repositório**, especificar assinaturas, arquivos e testes exatos. Não substituir o inventário por suposição.
5. Para economizar créditos do Codex, prefira `superpowers:executing-plans` no modo nativo por lotes com checkpoints e revisão final, em vez de subagente independente por microtarefa. Use `superpowers:subagent-driven-development` somente se houver orçamento/contexto suficiente.
6. Em cada tarefa: `superpowers:test-driven-development` (RED/GREEN/REFACTOR), `superpowers:systematic-debugging` quando aparecer defeito e `superpowers:verification-before-completion` antes de reportar resultado.
7. Revisar com `superpowers:requesting-code-review`, concluir com `superpowers:finishing-a-development-branch` apenas depois dos testes e de aprovação.

## Prompt inicial para colar no Codex

> Abra e leia integralmente `PLANO_SUPERPOWERS_TIBIA_TUDO_VOZ.md`. Aplique as skills do repositório `obra/superpowers` disponíveis neste ambiente, começando por `using-superpowers` e `brainstorming`. Sua PRIMEIRA tarefa é inventariar o código atual de reconhecimento/assistente de voz do Tibia Tudo, confirmar dependências, caminhos e estado real das funcionalidades, recuperar os testes existentes e atualizar o plano com arquivos reais. Use `writing-plans` para torná-lo executável e `executing-plans` para implementação nativa em tarefas pequenas, TDD e commits separados. Regra indispensável: a ativação ocorre SOMENTE após ouvir as três palavras completas HEY TIBIA TUDO, nessa ordem; TIBIA TUDO isolado jamais ativa, transcreve comandos ou chama a API. Crie testes positivos e negativos antes de alterar o detector. Preserve todos os timers e cálculos existentes. Não exponha chave OpenAI no cliente. Confirme modelos disponíveis/preços oficiais antes de escolhê-los. Não implemente nem faça deploy até concluir inventário, revisão de especificação e baseline. Não invente funcionalidade já implementada. Mostre resultados comprovados por testes e medidas, não por suposições.

## Fontes metodológicas

- https://github.com/obra/superpowers
- https://github.com/obra/superpowers/blob/main/skills/writing-plans/SKILL.md
- https://developers.openai.com/api/docs/pricing
