# Timers: análise do TibiaVision e implementação

## Referência verificada

Artefato local: `Y:\TibiaVision\TibiaVision.dll`, assembly 3.3.0.0, .NET 8.
SHA-256: `62fc8acdeefaae2a5cb6e2d926a6e259715e8f35d67436f1c469555902ea3806`.

A inspeção estática REA registrou o assembly e suas dependências WPF: Evidence `ev_08dc390e74fc7f1ecc5f82fb8d4eeb71a14593f44a127c4a1e0176d96dee7813`.
A inspeção de membros REA ficou indisponível por limite de representação de metadados de 64 MiB: Evidence `ev_f8880f376362fade6df3aff9d11e0084ed1ea6fb9a3d53f8b4d1d787cdedd558`. Isso não demonstra ausência de membros.

Para responder às questões específicas, ILSpyCmd 11.1.0.9782 recuperou a representação C# somente de `WindowReplicaApp.Views.TimerAlertOverlay` e `WindowReplicaApp.Views.CountdownBarWindow`, sem executar o aplicativo de referência. Os arquivos temporários foram `vision-alert.cs` e `vision-bars.cs` em `%TEMP%`.

Observações diretas dessa representação:

- `TimerAlertOverlay` usa Nunito Bold e WPF `DropShadowEffect`, `ShadowDepth=0`, `BlurRadius=22`, mesma cor do texto e `Opacity=0.85`. Essa configuração produz o halo percebido como glow.
- O alerta é transparente, fica no topo, não aparece na barra de tarefas, não ativa a janela e permite passagem do mouse. Há animações de opacidade.
- `CountdownBarWindow` usa borda branca de 1,5, cantos arredondados de 3 e preenchimento translúcido com alfa 160. A contagem altera a largura; também suporta orientação e lados na implementação de referência.
- A opção `gradient` altera a cor conforme a fração restante, de verde a amarelo/vermelho; a cor não é um gradiente espacial. A atualização é animada em 65 ms.

Não foi executado o TibiaVision nem observado seu comportamento ao vivo. A representação decompilada não equivale ao código-fonte original.

## Decisões para nosso aplicativo

Antes, o alerta era desenhado via GDI, sem suavização, com oito cópias pretas deslocadas para formar a borda. O fundo dependia de cor-chave, inadequada para um halo suave com transparência.

A implementação própria usa bitmaps RGBA, máscaras suavizadas e desfoque gaussiano, entregues ao Windows por `UpdateLayeredWindow` com BGRA pré-multiplicado. Mantém `WS_EX_TRANSPARENT` e `WS_EX_NOACTIVATE`. O brilho se inspira no mecanismo observado; não tenta reproduzir pixel a pixel o efeito WPF.

O usuário pode escolher glow, contorno, sombra ou texto simples, além de fonte e raio do brilho. As fontes são Verdana, Segoe UI, Tahoma e Arial, disponíveis no Windows; a fonte Nunito e outros recursos do TibiaVision não foram copiados.

As barras oferecem quatro formatos, estilo independente do nome/tempo e cor opcional conforme a contagem. Aparência e posições das barras continuam compartilhadas entre os timers. Texto, mensagem, cor, tamanho, piscar e duração fixa do alerta pertencem a cada timer. A cor individual permanece compartilhada entre alerta e barra, como antes.

A tela divide ativação/contagem, som/momento do aviso, texto, barras e posições, com prévia ilustrativa e teste do desenho real. As configurações antigas mantêm contorno e Verdana; novos timers começam com glow e Segoe UI. Nenhuma duração, tecla, som, volume, modo, vínculo ou estado ativo é removido.

## Verificação

- Testes de migração com arquivo temporário, persistência de estilos, transparência do halo, BGRA pré-multiplicado e encaminhamento de estilos para piscar/testar.
- Testes existentes dos três modos, aviso antecipado, importação e vínculo com personagens.
- QA de navegador em larguras 1550 e 1000: todos os controles antigos presentes, seleção de estilo, envio à API e cancelamento sem alteração do timer original.
- Teste nativo Win32 dos quatro estilos, barras com glow e fade: 30 atualizações, sem capturar foco, com passagem do mouse e sem falhas de `UpdateLayeredWindow`.

O teste nativo usou a área de trabalho; não houve validação em tela cheia exclusiva do Tibia. Essa limitação já existia no overlay anterior.
