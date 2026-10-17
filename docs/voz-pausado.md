# Voz pausada

Em 16/10/2026 o usuário preferiu um chat de texto à voz. A voz foi **pausada, não removida**: nada foi apagado.

## O que foi pausado

- `web/voz.js`: o `boot()` não chama mais `mutate('voz_iniciar')`. A API cria `Servico(..., silencioso=True)`: não cria o speaker e bloqueia iniciar/escutar. Microfone, Vosk, Piper, SAPI e downloads não iniciam pelo chat. Um único watcher usa `Store.poll`; os avisos aparecem em texto na tela. Os avisos (timer, boss, stamina, mercado) também viram toast com som (`audio_tocar`, ou bipe de 880 Hz) em **qualquer aba** e notificação da bandeja (`web_api._notificar_aviso`): `voz.js` consulta `voz_estado` a cada 2 s fora do Assistente e mostra cada id uma só vez (ids existentes no boot não repetem). O formulário de timer manual, a lista de timers e o polling continuam.
- `web/index.html`: status e “Pausar microfone”, esfera, ajuda ⓘ e “Último comando” ficam em `<div id="voz-pausado" hidden>`. Continuam no DOM para o `voz.js` não quebrar, mas não aparecem.
- Continuam no código e nos testes: `voz.py`, `voice/`, as pontes `voz_*` do `web_api.py` e as rotas `/transcribe` e `/interpret` do Worker.
- O código de acesso online (Configurações) agora serve ao chat; a voz o reaproveita se for religada.

## Onde está a fala natural

- Spec: `docs/superpowers/specs/2026-10-16-assistente-fala-natural-design.md`
- Plano: `docs/superpowers/plans/2026-10-16-assistente-fala-natural.md`

## Como religar

1. Em `web/voz.js`, devolver `mutate('voz_iniciar');` ao `boot()`, antes do `refresh()` (e do `setInterval`); como `mutate` marca busy, pôr depois do refresh pode engolir a inicialização.
2. Na API `_voz_obter`, retirar `silencioso=True` ou passar `False`. O padrão da classe permanece `False` para a voz arquivada; com `True`, iniciar/escutar ficam bloqueados.
3. Em `web/index.html`, tirar o `hidden` de `<div id="voz-pausado" hidden>`.
4. Em `test_voz_ui.cjs`, a expectativa volta a ser que o boot chama `voz_iniciar` uma vez.

O chat (`chat.py`, `web/chat.js`) e a voz executam as intenções da IA pelo mesmo `chat.executar_intencao`.


## Snapshot separado e dados

A referência de voz é a **Beta 92**, tag `v1.0.31-beta.92.1`, commit `82038616551df6b391e3b389e07b1c5511f5877f`. O arquivo versionado foi guardado separadamente em `G:\Meu Drive\CLAUDE CODE\zandao tibia tools\projetos-arquivados\assistente-voz\assistente-voz-beta92.zip`, junto de um README. O ZIP não deve entrar no Git nem nos pacotes Beta. Dados pessoais e credenciais DPAPI não fazem parte desse arquivo.

Para consultar/recuperar, extraia o ZIP em outra pasta ou peça uma cópia/worktree da tag; não resete nem troque a branch do checkout compartilhado. Reaplique somente os arquivos necessários depois de revisar os deltas do chat e o modo silencioso. A voz arquivada usa SAPI (voz do Windows) para os avisos; Piper continua disponível no código de reconhecimento/voz, sem carregamento no chat.

O chat não grava conversa em disco. Negação/ambiguidade podem pedir apenas uma resposta da IA e nunca autorizam ações. Ações destrutivas vindas da IA exigem o comando explícito ou formulário; comandos locais existentes continuam disponíveis. Trocar personagem/mundo limpa o contexto da conversa. Mensagens anteriores enviadas à IA são contexto, não autorização para repetir ações.


## Canais do chat

**Tudo IA** é o canal inicial: comandos locais primeiro; outras perguntas sobre Tibia/Tibia Tudo vão ao Worker. **Local Chat** executa somente os comandos locais e não manda suas mensagens nem respostas ao histórico da IA. **Server Log** é somente leitura e reúne eventos confirmados do Store e alertas do monitor já existente; não lê o chat ou o log do cliente Tibia. Os demais módulos continuam disponíveis nas abas próprias.

A aparência dos canais usa linhas compactas sobre fundo escuro. Enquanto a resposta está pendente há um indicador de digitação, sem segunda chamada automática. Trocar personagem ou mundo limpa as conversas e impede que uma resposta antiga apareça no perfil novo. Para o Tudo IA conversar com a OpenAI é necessário publicar a rota /chat do Worker; a Beta por si só não publica o servidor.
