# Voz pausada

Em 16/10/2026 o usuário preferiu um chat de texto à voz. A voz foi **pausada, não removida**: nada foi apagado.

## O que foi pausado

- `web/voz.js`: o `boot()` não chama mais `mutate('voz_iniciar')`. Microfone, Vosk e Piper nunca iniciam sozinhos. O formulário de timer manual, a lista de timers e o polling continuam.
- `web/index.html`: status e “Pausar microfone”, esfera, ajuda ⓘ e “Último comando” ficam em `<div id="voz-pausado" hidden>`. Continuam no DOM para o `voz.js` não quebrar, mas não aparecem.
- Continuam no código e nos testes: `voz.py`, `voice/`, as pontes `voz_*` do `web_api.py` e as rotas `/transcribe` e `/interpret` do Worker.
- O código de acesso online (Configurações) agora serve ao chat; a voz o reaproveita se for religada.

## Onde está a fala natural

- Spec: `docs/superpowers/specs/2026-10-16-assistente-fala-natural-design.md`
- Plano: `docs/superpowers/plans/2026-10-16-assistente-fala-natural.md`

## Como religar

1. Em `web/voz.js`, devolver `mutate('voz_iniciar');` ao `boot()`, antes do `setInterval`.
2. Em `web/index.html`, tirar o `hidden` de `<div id="voz-pausado" hidden>`.
3. Em `test_voz_ui.cjs`, a expectativa volta a ser que o boot chama `voz_iniciar` uma vez.

O chat (`chat.py`, `web/chat.js`) e a voz executam as intenções da IA pelo mesmo `chat.executar_intencao`.
