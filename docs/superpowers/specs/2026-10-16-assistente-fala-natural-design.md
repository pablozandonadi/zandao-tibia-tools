# Assistente Tibiano — fala natural (design)

Data: 16/10/2026. Status: aprovado em conversa, parte por parte; aguardando a revisão desta spec.

## 1. Objetivo

O usuário quer falar de forma natural durante o jogo e o assistente acertar a ação. Quando ele não tiver certeza, deve perguntar em vez de chutar.

**O que o usuário disse:**
- "Eu falo uma coisa, ele entende outra; quero falar normalmente, sem frases padrão."
- As frases da aba Instruções continuam valendo, mas com tolerância ("se mudar uma vírgula, ele entende também, tipo um contexto").
- Na dúvida: **perguntar por voz** (escolhido).
- **Memória curta** do assunto anterior (escolhido).
- Caminho **C (híbrido)**, em 4 entregas (escolhido).

**O que é suposição (não confirmado):**
- O usuário não sabe se o erro vem da escuta (transcrição) ou do entendimento. O design ataca os dois e põe "Entendi: …" na tela para tornar isso visível.
- O reconhecimento online (OpenAI) pode ser o principal; o offline (Vosk) é reserva.

**Restrições:** português do Brasil; resposta rápida; teto de gasto atual (US$ 0,20/dia global, US$ 0,05/dia por usuário); nenhum áudio ou texto falado gravado; o `Store` e as abas atuais não mudam; publicação pelo fluxo do AGENTS.md (Beta em `develop` por cópia temporária).

**Critério de sucesso:**
- ≥ 90% de um corpus de ~100 falas naturais entendidas **sem a IA**.
- 100% das frases da aba Instruções, com as variações, continuam passando.
- Toda ação que grava, quando houver dúvida, é confirmada antes de executar.

## 2. Referência externa (pesquisa com REA)

Alvo: os pacotes publicados do Home Assistant Assist no PyPI, baixados numa pasta isolada, sem executar nada deles.

| Pacote | Licença | Evidência REA |
|---|---|---|
| `home_assistant_intents-2026.10.6` (frases de 65 idiomas, incluindo `pt-BR`) | Apache-2.0 | inventário `ev_fa88ec51…`; extração `ev_34118c40…` |
| `hassil-3.12.1` (motor que casa frase com intenção) | Apache-2.0; depende de `PyYAML` e `unicode-rbnf` | extração `ev_45529eac…` |

**Observado nos arquivos:**
- As frases são **modelos com alternativas e partes opcionais**, ex.: `(cancela[r]|elimina[r]|aborta[r]) [o |a ][meu |minha ]<timer>`.
- Há **regras reutilizáveis** (`<timer>` = alarme/cronômetro/timer/temporizador), **palavras ignoradas** (`por favor`, `pode`) e **listas** (`timer_name`, `timer_minutes`).
- `recognize()` aceita `slot_lists`, `skip_words`, `intent_context` (contexto) e `allow_unmatched_entities`, que diz qual nome não foi reconhecido em vez de chutar.
- `fst.py` (`intents_to_fst`) gera a gramática a partir dos modelos, o que serve para um reconhecedor offline.
- Existe a intenção "deixa pra lá" (`HassNevermind`).

**Inferido (não observado nestes pacotes):** o Home Assistant tenta os modelos locais primeiro e chama a IA só como reserva. Isso vem do comportamento conhecido do Home Assistant, não dos arquivos analisados.

## 3. Fluxo

```
Microfone
  → Vosk (offline): detecta "Hey Tibia Tudo" (sem internet, também entende o comando — gramática gerada dos modelos)
  → OpenAI transcreve, com vocabulário do Tibia
  → ENTENDEDOR: 1) modelos de frase (hassil) + listas  2) senão, IA do Worker com descrições, candidatos e assunto anterior
               3) nome de boss aproximado; se houver dúvida → pergunta
  → DIÁLOGO: memória de ~1 min + pergunta pendente (sim/não, 8 s)
  → Store.execute (sem mudança)
  → resposta falada + tela "Ouvi / Entendi / Resposta"
```

## 4. Peças

| Peça | Novo/alterado | Responsabilidade | Interface | Entrega |
|---|---|---|---|---|
| Vocabulário | alterado: `voice/remote_ai_client.py`, `server/voice-worker/worker.mjs` | Envia à transcrição até ~150 tokens: termos do Tibia + bosses com kills no personagem + bosses usados há pouco | `transcribe(wav, request_id, vocabulario)` → o Worker repassa como `prompt` | 1 |
| Tela "Entendi" | alterado: `web/voz.js`, `web/index.html`, `voz.py` (`estado()` ganha `entendi`) | Mostra a ação entendida em linguagem humana | `estado()['entendi']` (texto) | 1 |
| Diálogo | novo: `dialogo.py` | Memória de ~1 min por personagem; pergunta pendente com prazo | `Dialogo.aplicar(resultado, agora) → Resultado`; `Dialogo.responder(texto, agora) → Resultado \| None`; `Dialogo.limpar()` | 2 |
| Modelos de frase | novo: `voice/frases_pt.yaml` | Frases em português no formato do hassil, para todas as ações atuais | arquivo de dados empacotado | 3 |
| Entendedor | novo: `entendedor.py` | Texto → ação + argumentos + certeza + o que faltou | `entender(texto, agora, catalogo, contexto) → Resultado(intent, args, certeza: 'alta'\|'media'\|'baixa', faltando, candidatos)` | 3 |
| Gramática offline | alterado: `voice/spike_assistente.recognition_grammar` | Gera a gramática do Vosk a partir dos modelos e das listas | mesma função, nova fonte | 3 |
| IA do Worker | alterado: `worker.mjs`, `voice/domain_actions.json` | Descrição de cada ação + candidatos + assunto anterior; continua só como reserva | `/interpret {text, candidatos, contexto}` | 4 |
| Orquestração | alterado: `voz.py` | Entendedor → diálogo → `Store.execute`; IA só se o entendedor não resolver | `Servico.comando()` | 1–3 |

Até a entrega 3, `assistente_tibiano.parse` continua sendo o entendedor local. Depois ele fica só como reserva e é removido quando o corpus provar paridade. Dependências novas na entrega 3: `hassil`, `PyYAML` e `unicode-rbnf`, fixadas em `requirements-build.lock` e incluídas no PyInstaller.

## 5. Diálogo

**Certeza:**
- **alta** — a frase bateu num modelo e o nome é exato ou um apelido conhecido → executa.
- **média** — nome de boss aproximado (difflib ≥ 0,85) **ou** ação interpretada pela IA → consulta executa; ação que grava pergunta "Você quis dizer X? Sim ou não?".
- **baixa** — dois ou mais candidatos → "Qual boss: A ou B?"; a próxima fala é o nome.

**Consultas nunca pedem confirmação.** A resposta sempre repete o que foi entendido ("Drume: libera em 3h").

**Pergunta pendente** (8 s, sem "Hey Tibia Tudo"):
- "sim", "isso", "pode", "confirma" → executa;
- "não", "cancela" → "Tudo bem, nada feito.";
- um nome → completa e executa;
- outra frase → vira comando novo e a pendência é descartada.

A regra atual de negação ("não …" aborta) **não** se aplica à resposta de uma pendência.

**Memória curta** (~60 s, só em memória, zera ao trocar de personagem):
- "e o Oberon?" → mesma intenção, outro boss;
- "mais 2 minutos" e "cancela ele" → último timer;
- "desfaz" → desfaz a última ação que gravou, quando houver forma suportada (abate → `boss.kill.undo`; timer criado → `timer.cancel`). Senão responde: "Não dá para desfazer isso por voz; use a aba."

## 6. Erros e custo

- **Sem internet / Worker fora:** modo offline (após a entrega 3 cobre todos os modelos); avisa uma vez.
- **IA inválida ou inventando data:** mantém `valid_intent` e `safe_temporal_intent` → "não entendi" + sugestões.
- **Limite diário atingido:** modo local + aviso.
- **Custo:** a IA só é chamada quando o entendedor não resolve (menos chamadas que hoje). O modelo continua o GPT nano; a troca é configuração do Worker (`VOICE_NLU_MODEL`), sem nova versão do app.
- **Privacidade:** nenhum áudio, transcrição ou memória do diálogo é persistida.

## 7. Testes

1. Frases da aba Instruções + variações (`test_instruction_phrases_tolerate_small_changes`) continuam verdes em todas as entregas.
2. Corpus `voice/frases_teste.yaml` com ~100 falas naturais → ação esperada. Inclui os casos reais de 16/10: "Quando minha estamina estará cheia?", "Vou fazer logout agora, minha estamina está em quarenta e uma horas.", "drumi". Meta: ≥ 90% sem IA.
3. `test_dialogo.py`: sim/não, prazo de 8 s, nome como resposta, "e o Oberon?", "mais 2 minutos", "desfaz", troca de personagem.
4. Worker: `test_worker.mjs` cobre vocabulário, instruções e corpo ≤ 12000 bytes.
5. Teste com microfone pelo usuário a cada Beta (não automatizável aqui).

## 8. Entregas (cada uma com Beta própria)

1. **Ouvir melhor + "Entendi" na tela** — vocabulário na transcrição; linha "Entendi". Exige deploy do Worker (com o ok do usuário).
2. **Pergunta por voz + memória curta** — `dialogo.py` sobre o parser atual.
3. **Modelos de frase + offline completo** — `frases_pt.yaml`, `entendedor.py`, gramática Vosk gerada; meta do corpus.
4. **IA com descrições** — absorve a sessão "Melhorar instruções da IA de voz no Worker" (interrompida na queda de energia, com mudanças pequenas e testes verdes, sem deploy).

## 9. Fora do escopo

Trocar a palavra de ativação; IA local (Ollama/qwen); voz ElevenLabs; leitura de dados do cliente do Tibia; arquivamento automático do histórico.

## 10. Coordenação

- A pasta é compartilhada com o Codex e com outras sessões do Claude: cada entrega lista os arquivos que vai tocar, e nenhuma outra sessão mexe neles ao mesmo tempo.
- A sessão "Terminar lista completa de bosses (539) e Beta" mexe em `assistente_tibiano.py`, `web/assistente.js` e `web/index.html`: a entrega 1 só começa depois que ela publicar.
- O `worker.mjs` da pasta principal já tem mudanças não publicadas da sessão interrompida (instruções da IA). A entrega 1 começa revisando essas mudanças: ou entram junto no mesmo deploy, ou são guardadas para a entrega 4. Nunca publicar o Worker com mudança que ninguém revisou.
- "Bosses usados há pouco" (vocabulário) = bosses citados por voz ou pela tela nos últimos 60 minutos da sessão do app, só em memória.
