# Tibia Tudo — baseline e próximos lotes de voz Implementation Plan

## Validação operacional — 16/10/2026

Após o proprietário adicionar créditos, o teste real passou: autenticação 401/401/400; três comandos sintéticos em português produziram timers de 20, 120 e 90 segundos; reenvio com UUID em maiúsculas retornou 409; GPT-5 Nano retornou intenção estruturada de timer de 90 segundos com HTTP 200. Worker e0c2436e-e124-4a78-a2d4-e6403c1bf199. A falha anterior insufficient_quota foi superada. Sem microfone, reprodução ou gravações pessoais; este smoke não substitui benchmark acústico com pessoas.

Nano usa até 2048 tokens e reserva conservadora de 2000 microUSD; respostas completas do provedor podem ter até 32 KiB por incluírem o esquema, enquanto a resposta ao aplicativo continua limitada a 8 KiB. Chave central somente no Worker; opt-in desligado em instalações novas. Acesso individual do proprietário configurado no perfil Beta do Windows.

Esta entrega cobre a fundação de voz. Os cinco módulos adicionais aprovados no PDF estão em uma etapa posterior da mesma tarefa e não são declarados implementados nesta versão. As notas abaixo preservam o histórico anterior.


> **For agentic workers:** usar `superpowers:executing-plans` em lotes com checkpoints; respeitar o fluxo de agentes autorizado para o projeto, sem delegação por microtarefa. Checkboxes registram somente evidência concluída.

**Goal:** tornar o plano executável a partir do código real, preservando timers/UI e executando o lote local autorizado pelo proprietário.
**Architecture:** manter serviço local, parser, Piper e ponte existentes; corrigir wake/captura antes da integração OpenAI protegida. Gateway requer decisões do proprietário.
**Tech Stack:** Python, unittest, pywebview, JavaScript/Node; Vosk 0.3.45, sounddevice 0.5.5 e piper-tts 1.3.0 fixados em `requirements-build.lock`.
**Spec:** [rascunho para revisão](../specs/2026-10-16-tibia-tudo-voice-ai.md).

**Decisão do proprietário:** gpt-4o-mini-transcribe + família GPT Nano + Piper TTS. Identificador Nano, suporte e acesso da conta a validar; gpt-5-nano constava depreciado na conferência documental. A sugestão anterior gpt-5.6-luna não está aprovada. A decisão de modelos não aprova todo o desenho nem resolve hospedagem, login e orçamento.

## Global Constraints

- Execução local autorizada em 16/10/2026; preservar dependências, dados pessoais, versão e build neste lote. Nuvem desligada; publicação pertence à coordenação.
- Preservar checkout compartilhado, branch e alterações de outras pessoas; timers continuam efêmeros e compartilhados entre voz/formulário.
- HEY + TIBIA + TUDO completos, na ordem e mesma emissão; sem wake válido, zero transmissão cloud ou execução.
- Sem chave central no cliente; IA cloud desligada sem autenticação e orçamento explícitos. Voz local continua iniciando como hoje.
- Nomes novos no plano original são sugestões: não criar controller/router/actions paralelos se os módulos atuais comportarem o trabalho.

## Review Focus

1. Vosk omite a primeira palavra: teste acústico deve provar wake, não apenas teste de regex.
2. TTS e limpeza da fila cortam comando que vem logo após ativação: testar mesma frase e pausa natural.
3. Dois timers iguais: preservar ID do card e exigir esclarecimento por voz antes de apagar.
4. Retry após timeout: uma intenção não pode criar dois timers.
5. Serviço indisponível ou falha de microfone: UI, timers e fallback local continuam utilizáveis.

## Evidência de 16/10/2026

- [x] Inventário e testes atuais recuperados pela coordenação; fonte base `main`, SHA `c593f4c6584c1a163f3e93c9b0ceff5ab93bc5c4`.
- [x] Estado inicial compartilhado registrado: 198 entradas modificadas/não rastreadas antes desta documentação; cópia temporária das fontes de voz para restauração, sem credenciais/dados pessoais. SHA não descreve as alterações locais.
- [x] Stack, entrypoints, timers/shared, captura, Piper e frontend mapeados na especificação.
- [x] Ausência de gateway/auth próprios registrada; não é autorização para criar infraestrutura pública.
- [x] Proprietário autorizou “execute o plano” e esfera/clique sem wake; servidor escolhido para proteger segredo central. Decisões operacionais cloud ainda pendentes.

Com ambiente Python de voz ativado e Node disponível, na raiz:
```powershell
python -B -m unittest test_voz voice.test_spike_assistente test_voz_credenciais -v
node test_voz_ui.cjs
```
Resultado observado pela coordenação: **32 testes Python passaram em 0,432 s** (9 serviço, 20 spike, 3 credenciais); UI Node passou em autostart, criar, cancelar, polling e texto seguro.
São regressões existentes com mocks, não prova de microfone real, rede ou requisitos novos. `test_voz_credenciais` usa dados falsos; credenciais pessoais não foram abertas.

Sonda textual do código atual, sem correção:
| Entrada | Observado | Esperado novo |
|---|---|---|
| `HEY TIBIA TUDO` | Ativa, comando vazio | Igual |
| `HEY TIBIA TUDO inicia timer de 30 segundos` | Extrai comando | Igual, confirmar execução no futuro teste |
| `TIBIA TUDO` | **Ativa indevidamente** | Ignorar |
| `TIBIA TUDO inicia timer de 30 segundos` | **Extrai comando indevidamente** | Ignorar sem execução |
| `HEY TIBIA`, `HEY TUDO`, `HEY`, conversa mencionando `TIBIA TUDO` | Ignora | Igual |
| `coloca um timer de um minuto e meio` | Rejeita; lista de timers vazia | Criar 90 s |

`command_after_wake` usa prefixo opcional e `recognition_grammar` inclui wake incompleto. `dispatch` cancela o mais recente entre durações duplicadas, em conflito com a nova exigência de esclarecimento.
`shared_reply` calcula fórmula própria; deverá delegar a `tibia_info.faixa_shared`, preservando resultado. Vocativo repetitivo continua no código.

### Sonda local de desempenho, sem microfone nem reprodução

Medição única pela coordenação, Python 3.12.14, modelos locais já em cache (Piper Faber e Vosk português small 0.3); áudio sintetizado em memória, sem gravação persistida:
| Medida | Resultado |
|---|---|
| Carregamento inicial Piper | 15,4736 s |
| Primeira síntese | 4,189 s, gerando 3,2276 s de áudio |
| Carregamento Vosk | 1,4974 s |
| Decode do áudio sintético | 0,2586 s |
| Roteamento textual determinístico, 100 chamadas | p50 0,0544 ms; p95 0,0646 ms |
| CPU acumulada do processo na sonda | 10,125 s |
| Working set observado | 311,16 MiB |
| Private bytes observados | 1.599,74 MiB; memória privada comprometida, não RAM residente |

Transcrição obtida: `tíbia tudo ligar um temporizador de noventa segundos`; a primeira palavra “Ei” foi perdida. Isso demonstra limite acústico atual e **não** satisfaz a regra obrigatória de três palavras.
O p50/p95 mede somente roteamento textual; não mede fim da fala até resposta. CPU é tempo acumulado, não porcentagem nem consumo em repouso. Uma sonda fria não é benchmark estatístico de voz.
- [ ] Medir microfone real, corte de início/fim, ruído, eco, p50/p95 ponta a ponta, CPU/RAM com jogo e custo real de API.
- [ ] Adicionar teste de integração RED do fluxo de 90 s com áudio mockado; a sonda textual não substitui esse teste.
**Task 1 do plano original permanece parcial.**

## Lotes futuros — somente após aprovação da especificação

### Lote 1 — RED do wake e timer natural; sem nuvem

**Arquivos:** `voice/test_spike_assistente.py`, `test_voz.py`; eventual teste de captura junto ao serviço existente. Produção: `voice/spike_assistente.py` e `voz.py` somente após RED.
**Interfaces:** preservar `command_after_wake(text) -> None | str`, `dispatch(text, data_dir, timers, now, state=None)` e `Servico.comando/criar/cancelar/estado`.
- [ ] Acrescentar casos nomeados de wake completo, bare/incompleto, menção no meio, comando na mesma frase e resposta do próprio Piper; entradas inválidas não chamam nuvem nem alteram timers.
- [ ] Acrescentar `um minuto e meio == 90 s`, `meio minuto == 30 s`, limite 10.800 s, negação, bool/NaN/infinito e cancelamento duplicado sem remoção.
- [ ] Rodar testes novos, registrar RED esperado; não contar falha de import/ambiente como reprodução do defeito.
- [ ] Implementar mínimo nos pontos compartilhados; repetir os dois comandos de regressão acima e casos novos até GREEN.
- [ ] Revisar impacto nos callers/UI antes de naturalizar respostas ou alterar o formato interno de timer.

### Lote 2 — captura e feedback local

**Arquivos:** `voz.py:Servico._listen/_reply/_say_loop`, `voice/spike_assistente.py:PiperSpeech`; `web/voz.js` e `test_voz_ui.cjs` só se necessário para estados.
**Interfaces:** manter ponte `web_api.py:voz_iniciar/parar/estado/criar/cancelar` e snapshot atual, acrescentando estados somente com compatibilidade dos callers.
- [ ] Criar RED para pausas internas, pre-roll, fim de frase, overflow, fala junto ao wake, TTS sobreposto e microfone indisponível.
- [ ] Ensaiar parâmetros propostos 0,5/0,8/15 s, sem nova dependência antes de avaliar recursos instalados. Documentar decisão de VAD e detecção acústica das três palavras.
- [ ] Implementar GREEN e validar com áudio consentido e microfone real; sem resultado acústico satisfatório, registrar limitação e não relaxar wake.

### Lote 3 — gateway e IA protegida

**Arquivos futuros:** definir caminhos de backend após proprietário escolher hospedagem/auth; `voz.py` será consumidor de cliente limitado, não armazenador da chave central. Não criar o mapa ilustrativo `server/` como se existisse.
**Interfaces:** contratos relativos `/v1/voice/transcriptions` e `/v1/voice/interpretations` da spec, com autenticação e `request_id`; ações locais validadas antes da execução.
- [ ] Fechar proprietário do gasto, quotas, orçamento, hospedagem, login/token e retenção. Validar acesso a `gpt-4o-mini-transcribe` e identificador/suporte do GPT Nano escolhido; os preços documentais não comprovam acesso.
- [ ] Criar testes com gateway falso para limites WAV/texto, schema extra/inválido, 401/403/413/429/5xx, timeout, replay e retry sem duplicar timer.
- [ ] Só então planejar arquivos/assinaturas definitivos do backend e testes; nenhuma implantação antes das decisões/aprovação.
- [ ] Benchmark do mesmo corpus PT-BR, offline/rede ruim, revisão de segurança e rollback precedem rollout Beta; estável permanece dependente de aprovação específica.

## Ledger e método de execução

Para cada lote registrar arquivos, RED/GREEN, resultado observado, limitações e decisão de seguir/parar. O plano original continua sendo o roteiro macro; este documento fixa caminhos reais e a ordem imediata, sem alegar plano de backend concluído.
A preferência do plano por execução nativa em lotes permanece registrada; aplicar a política autorizada de explorador → programador → revisor para mudanças médias/grandes e não delegar novamente dentro de subagentes.
Concluído nesta fase: inventário, baseline parcial e rascunho documental. Pendente: revisão humana, integração RED de áudio e validação acústica/infraestrutura. Sem commit, push, publicação ou alteração do aplicativo nesta entrega.

## Execução do lote local — 16/10/2026

O histórico de baseline acima descreve o estado anterior. Lote local agora implementado para revisão: wake obrigatório, 90/30 s naturais, limite 1..10.800 s, negação sem ação, duplicados sem remoção, último explícito, tempo restante e shared pela função existente. Formulário mantém limite anterior de 1..180 por unidade.

Sessão por wake/clique dura 8 s; após ação requer novo wake. Esclarecimento aceita somente duração/último pendente e expira. Esfera CSS é botão nativo com aria, foco e reduced-motion, estados retornados pelo serviço; start automático/poll somente aberto e pausa manual preservados.

Captura PCM: pre-roll 0,5 s, silêncio final 0,8 s, teto 15 s sem executar truncamento; energia fixa com limitação comentada. Overflow descarta captura/sessão, TTS não autoativa e microfone indisponível deixa timers intactos. Não grava nem transmite áudio.

**RED observado antes das correções:** wake bare/oi retornava comando; natural 90 s não criava timer; cancelamento abreviado/remaining falhavam; sessão não criava timer no stub; Capture não emitia segmento e não preservava áudio; Node não tinha handler da esfera. RED adicional: clique em preparação abria sessão, teto devolvia áudio truncado e esclarecimento aceitava ordem nova (3 timers em vez de 2).

**GREEN:** `python -B -m unittest test_voz voice.test_spike_assistente voice.test_audio_capture test_voz_credenciais -q` — 45 testes passaram. `node test_voz_ui.cjs` — autostart, esfera, estados, criar/cancelar, polling aberto e transcrição segura passaram. Áudio PCM mockado percorre callback/segmentação/Vosk falso/dispatch e cria 90 s com início/fim e pausa interna de 500 ms preservados. Esse teste integrado foi adicionado como verificação após RED dos componentes; não houve RED integrado de 90 s antes da produção.

**Limites:** sem microfone real, gravações privadas, reprodução real, benchmark ponta a ponta ou validação visual em navegador. Sonda Vosk anterior perdeu “Ei”; detecção acústica segue não comprovada. Gateway, acesso aos modelos e custos reais não implementados neste lote. Nenhum commit/push/publicação pelo programador; revisão independente pela coordenação pendente.

Validação ampla: `python -B -m unittest discover -q` — **639 testes passaram em 21,644 s**. Emitiu ResourceWarning preexistentes de arquivos sem fechamento em `test_hunt`, `test_itens_set`, `test_proficiencia`, `test_stats_set` e `test_world_board`; nenhum teste falhou. `git diff --check` global apontou somente linha em branco preexistente em `instalador/gerar_instalador.ps1:99`, fora deste lote.

## Gateway e cliente preparados — 16/10/2026

Estado anterior acima é histórico do lote local. Tasks3..6 agora têm implementação pronta para revisão/operação, sem declarar benchmark concluído: Cloudflare Worker+singleton SQLite DO; STT mini-transcribe; Nano estruturado; cliente fixo com DPAPI; opt-in UI OFF; autorização acústica por wake/clique e corte do wake mesmafrase com timestamps Vosk; dispatcher local antes de Nano. A coordenação comunicou primeiro deploy OFF; acesso/uso real da conta e ativação são verificação separada.

RED adicional observado: burst inválido não limitava; provider JSON null retornava503; STT reservava estimativa50micro em vez do pior caso30000; uso válido não liquidava e concorrência permitia gastar acima do teto; UUID com maiúsculas contornava replay; nova ordem comwake durante esclarecimento criava terceirotimer; TTS longo expirava seleção e seleções contextuais eram ignoradas. Corrigidos com testes de regressão.

GREEN: **656 testes Python** em14,706s com `Z:/Temp/tibia-tudo-voice-spike/venv/Scripts/python.exe -B -m unittest discover -q`; **19 testes gateway Node** com SQLite real em15,402s; NodeUI GREEN. ResourceWarning preexistentes nos mesmos testes listados acima. Uma primeira execução usando o Python bundled sem dependências falhou45erros(webview ausente) e1timingmirror; o runtime correto passou a suíte inteira sem essa falha, sem alterar Mirror/dependências.

Sem microfone real, teste acústico/corpus, reprodução real ou chamada OpenAI pelo programador. Testes de integração usam PCM sintético, Vosk e OpenAI falsos. Revisão final, contas, implantação, publicação Beta e artefatos oficiais ficam com a coordenação; nenhum commit/push/deploy pelo programador. Orçamento e contratos detalhados no README do gateway.

### Verificação final após revisão e transporte

Suíte final `Z:/Temp/tibia-tudo-voice-spike/venv/Scripts/python.exe -B -m unittest discover -q`: **659 testes GREEN em13,206s**. Gateway: **22 testes Node GREEN em15,478s**, incluindo diagnóstico allowlist e binding de fetch. NodeUI GREEN e whitespace dos arquivos rastreados do escopo sem apontamentos. ResourceWarning preexistentes persistem, sem falhas.

Coordenação realizou smoke sem microfone: infraestrutura/autenticação reais passaram; chamadas OpenAI foram bloqueadas por **429 insufficient_quota**, confirmado via diagnóstico no deploy `08a268d0`, em16/10/2026. Não considerar Task4/5 ou qualidade/custo real validados. Serviço OFF até regularização da conta; programa preparado com fallback local e opt-in OFF. Não houve credencial lida pelo programador, commit/push/deploy ou gravação real neste lote.
