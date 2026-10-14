# Mirror — implementação e validação

A seção Mirror oferece quadrado padrão de 32 × 32 pixels físicos e seleção manual, ambos com lupa. A roda ajusta opcionalmente o quadrado; setas movem a seleção e Ctrl+setas ajustam o tamanho. Enter confirma a seleção manual e Esc cancela. A opção Cancelar seleção também funciona enquanto o painel aguarda o Tibia em primeiro plano.

Escolha um personagem em uso, crie um perfil e vincule o cliente Tibia. Se houver apenas um cliente identificável, o aplicativo o vincula na sessão; com vários, escolha explicitamente a janela. Cada personagem mantém seus próprios perfis. Duplicar um perfil cria recortes independentes. Aumentar a escala de exibição preserva a região de origem.

Cada recorte permite nome opcional, visibilidade, trava, opacidade, cor livre e glow desligado/mínimo/médio/máximo. Destrave para arrastar a posição sobre o Tibia; travado, o mouse passa pelo recorte. Imagem, nome e glow ficam ocultos ao sair do cliente vinculado. Uma mudança de tamanho ou DPI que invalide a origem pausa o recorte e permite reposicioná-lo. As coordenadas da captura são físicas e relativas à área cliente, não à moldura externa.

Perfis são dados pessoais em mirrors.json, no diretório de dados do canal. Gravação atômica, backup recuperável e integração com o backup do aplicativo. O pacote exclui o arquivo e seus temporários/backups. Não guarda imagens capturadas nem importa configurações pessoais do TibiaVision.

## Limites técnicos e regras

Este módulo apenas exibe conteúdo da janela via DWM e permite configuração manual de seus próprios overlays. Não envia teclas/cliques ao jogo, não executa ações de personagem, não lê/escreve memória do cliente, não injeta código, não modifica arquivos/protocolo do Tibia e não altera nem contorna sua proteção de captura. Os hooks temporários servem para receber a seleção manual e impedir que seus cliques cheguem ao jogo; são removidos ao cancelar, concluir ou perder foco. A consulta de processo usa somente a permissão de identidade PROCESS_QUERY_LIMITED_INFORMATION.

A regra oficial 3b proíbe manipular o cliente e usar software para executar ações de jogo automaticamente. Ela não fornece autorização explícita para esta implementação de Mirror; este documento não afirma aprovação da CipSoft ou ausência de risco de punição. A ausência de automação é um limite técnico verificável, não uma certificação de conformidade pela empresa.

Fonte oficial consultada em 14/10/2026: [Tibia Rules, regra 3b](https://www.tibia.com/support/?mobile-app=true&rule=3b&subtopic=tibiarules&theme=false).

Não foi tentado nenhum contorno do BattlEye ou da proteção do Windows. Se a composição do cliente não funcionar, informar a limitação. Não introduzir bypass, captura por injeção ou alteração de afinidade para corrigir imagem preta.

## Validação feita

- Testes de isolamento por personagem/perfil, duplicação com IDs independentes, persistência, recuperação de JSON inválido e esquema inválido, cancelamento/respostas antigas, limites de geometria/escala e encerramento.
- Testes de seleção reversa, ajuste fino, quadrado sem deformação, supressão do release de clique, foco por HWND exato, pausa por geometria/DPI, cache do halo e ciclo de vida Win32.
- Teste de fronteira técnica: os módulos Mirror não podem usar APIs de geração de input de jogo, memória, injeção ou alteração de proteção de captura.
- DWM nativo com fonte sintética: conteúdo verde correto, opacidade total/50% correta sobre azul; locked WindowFromPoint retornou a janela subjacente, unlocked retornou o mirror. Nenhum recurso GUI residual após encerrar.
- Cache: nenhum novo upload de glow em 30 ticks estáveis. Com 1/5/20 recortes sintéticos, atualização de controle média de aproximadamente 0,05/0,11/0,21 ms; são medidas locais do controle do overlay, não benchmarks de FPS do jogo.
- Navegador com tema do aplicativo e dados fictícios em 1550 e 430 pixels de largura: cor livre, cancelamento/espera, ausência de overflow horizontal e erros JS. Prévias: mirror-preview.png e mirror-mobile-preview.png.
- Revisão independente corrigiu passagem do mouse em host DWM, seleção sem cliente/cancelamento e deformação por Ctrl+setas. Nova revisão confirmou as correções.

O cliente Tibia local respondeu GetWindowDisplayAffinity com WDA_MONITOR (0x1). Screenshots de teste do cliente e da miniatura ficaram pretos; essa proteção impede usar essas capturas para concluir se o mirror visível está correto. A visualização com o cliente real exige conferência direta do usuário. Não foi validada a matriz física de monitores/DPI 100/125/150/200%, tela cheia exclusiva ou todo modo gráfico. A fonte sintética confirma o mecanismo nativo, não a compatibilidade universal do Tibia.

## Entrega

Código publicado por cópia temporária de develop, contendo somente o delta Mirror e suas dependências. A fonte compartilhada e os dados pessoais foram preservados. Beta oficial gerada pelo pipeline; canal estável somente após aprovação do usuário.
