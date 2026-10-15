# Seleção Mirror: precisão e resposta

15/10/2026. Plano aprovado após análise estática REA do Tibia Toolkit e revisão da arquitetura local.

- Lupa DWM: amostra padrão32×32 exibida200×200 com borda. No quadrado ajustado pela roda, acompanha a própria região; no manual, acompanha o cursor com amostra32×32.
- Seleção manual com oito alças e movimento pelo interior. Quadrado: clique posiciona; Enter confirma ambos; Esc cancela. Soltar o mouse fora após posicionar o quadrado não cancela o recorte.
- Quatro painéis Win32 pretos com alfa80 deixam a região escolhida clara. Antes do primeiro arraste manual, o cliente inteiro fica suavemente escurecido e a instrução aparece.
- Worker usa MsgWaitForMultipleObjectsEx e mensagens para despertar por entrada/comandos. Eventos marcam seleção dirty; desenho e limpeza ocorrem fora dos hooks. Sem imagem do cliente inteiro por frame.
- Preservadas políticas de foco, pixels físicos/DPI, dados pessoais, render DWM e proteção de captura. Não acrescenta geração de entrada ou acesso à memória do jogo.

Revisão independente encontrou e corrigiu início manual sem sombra e cancelamento ao soltar fora no quadrado. Suíte completa local:572 testes aprovados em cópia limpa. Selfcheck Win32 com janela sintética fora da área visível confirmou alpha80/LWA_ALPHA, TOPMOST/TRANSPARENT/NOACTIVATE, foco inalterado e HWND destruído. Prévias sintéticas verificadas. A matriz real de monitores/DPI, a interação com o Tibia e FPS/latência física não foram medidos; não alegar60FPS nem comparações medidas com o Toolkit.

Publicação Beta oficial pendente de conclusão do pipeline. Canal estável preservado.
