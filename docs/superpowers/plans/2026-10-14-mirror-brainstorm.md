# Mirror — brainstorm e plano proposto

Data: 14/10/2026. Estado: proposta de novo subsistema; sem implementação no aplicativo.
Método: brainstorming do Superpowers, com análise REA e decompilação estática complementar.

## Objetivo e requisitos confirmados

Criar uma seção Mirror no ZandaoTools para reproduzir ao vivo partes da janela do Tibia.

- Dois modos: quadrado padrão para ring, amulet e action bar; retângulo manual por arrasto.
- Lupa ao lado do cursor nos dois modos para alinhar o recorte com precisão.
- Nenhuma calibração obrigatória. O quadrado começa no padrão confirmado de 32 × 32 pixels físicos.
- Cada recorte oferece glow desligado, mínimo, médio ou máximo, com cor livre escolhida pelo usuário.
- Somente os mirrors do personagem em uso e de seu perfil selecionado ficam habilitados.
- Um personagem pode salvar vários perfis, por exemplo Hunt, Boss e Geral. Dois ou três não constituem limite obrigatório.
- Durante o uso normal, recorte, nome e glow aparecem somente com a janela Tibia vinculada em primeiro plano. Alt+Tab, minimizar ou fechar o cliente oculta tudo.
- Mudança de monitor exige tratamento explícito de DPI e coordenadas, sem presumir que a escala do jogo acompanha a escala do Windows.

## Evidências da referência

Artefato analisado: Y:\TibiaVision\TibiaVision.dll, assembly 3.3.0.0, .NET 8, WPF.
SHA-256: 62fc8acdeefaae2a5cb6e2d926a6e259715e8f35d67436f1c469555902ea3806.

REA inspect_managed_artifact: ev_08dc390e74fc7f1ecc5f82fb8d4eeb71a14593f44a127c4a1e0176d96dee7813.
Confirmou identidade, plataforma e metadados. Não decompila nem executa o assembly.
REA inspect_managed_members: ev_f8880f376362fade6df3aff9d11e0084ed1ea6fb9a3d53f8b4d1d787cdedd558.
Indisponível pelo limite de representação de metadados de 64 MiB. Não demonstra ausência de membros.

Complemento: ILSpyCmd 11.1.0.9782 recuperou apenas tipos relacionados ao fluxo, em pasta temporária zandao-mirror-analysis-20261014. Nenhum código ou recurso decompilado foi copiado para o projeto. As conclusões abaixo são observações da representação recuperada; não são observações de execução ao vivo.

| Questão | Observação estática |
| --- | --- |
| Tamanho padrão | CropSettings.OneClickBoxPhysicalPx = 32.0. É tamanho físico, não 32 DIP. |
| Ajuste do quadrado | FixedCropOverlayWindow converte o tamanho por DpiHelper.Scale. A roda altera 4 pixels por passo, entre 16 e 256; alterações podem ser persistidas. |
| Seleção manual | RegionSelectorWindow calcula retângulo por arrasto, suporta alças e abre CropMagnifierWindow. |
| Lupa | CropMagnifierWindow usa miniatura DWM, janela de 200 unidades lógicas, referência de zoom pontual 4× e afastamento de 28 unidades do cursor. Não pega foco e deixa o mouse passar. |
| Mirror ao vivo | RegionMirrorWindow usa DwmRegisterThumbnail e DwmUpdateThumbnailProperties com retângulo de origem, destino e fSourceClientAreaOnly. |
| Glow | RegionMirrorWindow utiliza três bordas; alfas base 64, 128 e 221. SetGlowIntensity mapeia intensidades para fatores 0,6, 1,0 e 1,5. Isso não comprova um desfoque gaussiano no Mirror. |
| Foco | WindowHelper.ShouldMirrorsBeVisible permite também o TibiaVision em primeiro plano. MainViewModel tem temporizações e exceções ao editar/desbloquear. Nosso requisito de uso normal será mais restrito. |
| DPI | DwmThumbnailHelper.GetSourceSpaceScale usa a relação entre o DPI da origem e a escala do aplicativo; origem e destino são convertidos separadamente. |
| Perfis | ProfileService salva/carrega coleções e restaura o último perfil. A análise focada não estabeleceu organização hierárquica por personagem; essa organização é requisito próprio. |

Imagem fornecida: 1920 × 1009 pixels. A ampliação sem interpolação mostra conteúdo de 32 × 32 nos slots, separado da moldura e do espaçamento. Exemplo mensurável da primeira célula horizontal da action bar: conteúdo x=372..403 e y=744..775, inclusive; 32 pixels em cada eixo. Isso confirma esta captura, sem provar o tamanho em toda escala/monitor.

Limites: não houve interação ao vivo com o TibiaVision, nem teste real de captura do Tibia, troca de monitor, consumo ou latência. Conteúdo de configurações pessoais da referência não foi necessário.

## Alternativas de implementação

1. **Recomendação: miniatura DWM + moldura/glow próprio.** O Windows compõe o recorte da janela Tibia; nosso código controla região, posição, escala, foco e perfil. Uma camada RGBA separada desenha glow e título. Evita capturar o próprio mirror e dispensa um loop Python copiando imagens para cada recorte. A composição entre miniatura e camada transparente precisa ser demonstrada primeiro.
2. **Captura de pixels em CPU.** Mais direta para processar a imagem com Pillow, mas exige atualização periódica, gerenciamento de buffers e prevenção de feedback se capturar a tela. Pode apresentar imagem preta em certos modos e consumir mais com múltiplos recortes. Reservar como alternativa caso o teste DWM falhe; não implementar dois motores antes da necessidade.
3. **Captura Windows Graphics Capture/GPU.** Alternativa para limitações reais da DWM. Integração e distribuição Python mais complexas; não é necessária para a primeira entrega se a DWM atender.

A referência torna DWM uma hipótese fundamentada; o protótipo no cliente real decide a viabilidade. Não prometer funcionamento em tela cheia exclusiva, superfícies protegidas ou todo modo gráfico antes desse teste.

## Fluxo da seção Mirror

Cabeçalho: personagem em uso, seletor de perfil, estado do cliente e comandos Novo perfil, Duplicar e Renomear. Perfil ativo é lembrado separadamente para cada personagem.

Ações principais: Quadrado padrão e Seleção manual. Lista de recortes com nome, visibilidade, trava, escala de exibição, opacidade, cor do glow, intensidade, Editar recorte e Remover. Incluir Ocultar todos e Travar/destravar todos no perfil atual. Nome acima do recorte é opcional e não faz parte da imagem capturada.

Quadrado: solicitar que o Tibia fique em primeiro plano; abrir seleção sobre sua área cliente, mostrar quadrado 32 × 32 e lupa; clique confirma, Esc cancela. Permitir ajuste opcional pela roda, como na referência, se a escala real do jogo demandar outro tamanho. Isso não introduz etapa de calibração. O padrão de novos recortes continua 32; tamanho personalizado pertence ao recorte.

Manual: arrastar em qualquer direção, visualizar a lupa e permitir ajuste fino de bordas antes de confirmar; Enter confirma e Esc cancela. Não criar registro parcial em caso de cancelamento.

Após confirmar: o recorte aparece em posição inicial dentro da área visível; o usuário posiciona, ajusta aparência e trava. Escala de exibição aumenta o mirror sem alterar a região de origem. Em uso normal, a trava permite passagem do mouse e a janela nunca ativa o foco.

Edição é um estado explícito e temporário: iniciada no painel, aguarda o Tibia em primeiro plano. Seleção recebe a entrada necessária sem transformar o painel em exceção permanente de visibilidade. Ao mudar para outro aplicativo, interromper/cancelar a seleção e ocultar lupa e overlays. Detectar o HWND do cliente vinculado, em vez de aceitar qualquer janela do mesmo processo. A implementação precisa testar o recebimento de mouse/teclas sem roubar o foco e sem enviar cliques de seleção ao jogo.

## Personagem, perfil e persistência

Hierarquia: personagem → perfis Mirror → recortes. Identificadores estáveis para perfis e recortes; compatibilizar o vínculo de personagem com o mecanismo existente em personagens.py e web_api.py. Renomear um perfil não perde posições nem altera os demais.

Dados propostos: versão do esquema; personagem; id/nome do perfil; id do perfil ativo; lista de recortes. Cada recorte guarda modo, região de origem relativa à área cliente, posição de destino relativa ao cliente, dimensões/escala de saída, nome, visibilidade, trava, opacidade e glow {habilitado, cor, intensidade}. Registrar contexto de geometria/DPI necessário para validar a restauração. HWND não é identificador persistente: deve ser resolvido novamente ao reabrir o cliente.

Salvar em mirrors.json pelo app_paths.data_dir(), com gravação atômica e recuperação de backup. Incluir o arquivo nas regras de dados pessoais, backup e exclusão de pacote/commit. Não guardar imagens da tela nem importar dados pessoais do TibiaVision. Ao trocar personagem, remover imediatamente os overlays antigos e carregar somente o perfil do novo. Sem personagem em uso, nada aparece.

Personagem em uso é a seleção existente do ZandaoTools; não pressupor leitura automática do personagem logado no Tibia. Com vários clientes, o usuário vincula explicitamente o cliente correto na sessão; nunca selecionar silenciosamente a maior janela para capturar outro personagem.

## Monitor, DPI e geometria

Separar três espaços: coordenadas cliente da janela Tibia, pixels físicos da origem e coordenadas do destino. Usar DPI da janela/monitor correspondente e tratar WM_DPICHANGED. Monitor pode ter origem negativa e origem/destino podem ter DPI diferentes.

32 pixels físicos não equivalem automaticamente a 32 DIP. Não aplicar 32 × DPI/96 cegamente ao recorte. O número de pixels de um slot pode permanecer 32 num cliente consciente de DPI; se houver escala da interface do jogo ou bitmap scaling, pode mudar. Conversão de coordenadas resolve virtualização, não reconhece automaticamente o tamanho de um slot.

Ao mover o cliente, acompanhar sua área cliente. Ao redimensionar ou mudar escala/layout, validar limites e geometria; não esticar proporcionalmente um recorte de ring e presumir que continuará alinhado, pois os painéis do Tibia podem se reorganizar. Em mudança incompatível, pausar o recorte afetado, indicar Reposicionar recorte e conservar sua configuração. A lupa e o ajuste opcional do quadrado atendem o encaixe sem calibração inicial obrigatória.

Posições de destino devem continuar visíveis ao desconectar monitor. Reposicionar para o monitor atual quando necessário. Espessura/glow da moldura pode seguir escala visual do destino, sem alterar o tamanho físico da região capturada.

## Glow próprio

Cor livre por seletor e hexadecimal. Quatro opções: Desligado, Mínimo, Médio e Máximo. Persistência individual por recorte/perfil.

Desenhar contorno fino e halo externo em RGBA pré-multiplicado, usando layered_image.py como infraestrutura. Gerar máscara e desfoque próprios; cachear por tamanho, cor, intensidade, DPI e formato. Não redesenhar o halo a cada frame do conteúdo. Três níveis devem ser distinguíveis pela força/extensão do halo e preservar nitidez do conteúdo; valores finais definidos por prévia nativa e capturas comparativas.

Reservar margem externa suficiente para o glow máximo. Ele não cobre pixels do item nem entra na região capturada. Sincronizar visibilidade, movimento e destruição da camada do glow com a miniatura e o nome, evitando bordas órfãs. Cor e intensidade do nome são independentes da imagem capturada; a primeira versão pode usar a cor do glow como padrão do título.

## Componentes e integração proposta

- mirror_core.py: validação, modelo, isolamento por personagem/perfil e persistência, sem depender do Win32.
- mirror_native.py: descoberta/vínculo do HWND, geometria, miniaturas DWM, foco, ciclo de vida e composição do glow.
- mirror_selector.py: quadrado, seleção manual, lupa e confirmação/cancelamento.
- web/mirror.js e web/mirror.css: seção e prévias dos controles; integração com web/index.html.
- web_api.py: operações de perfis/recortes e evento de personagem em uso; incluir Mirror na inicialização/encerramento.
- app_paths.py, backup.py e regras de pacote: tratar mirrors.json como dado privado.

Reutilizar princípios de overlay.janela_tibia_em_foco(), mas ampliar o resultado para preservar HWND e área cliente. Não usar janela_do_tibia() como único vínculo: ela retorna a maior janela visível. A função de foco atual devolve retângulo externo; isso é insuficiente para um recorte preciso da área cliente. Preservar os timers e demais alterações existentes.

## Dificuldades e como resolvê-las

| Dificuldade | Critério de resolução |
| --- | --- |
| Captura compatível com Tibia | Testar DWM no cliente real, em janela e sem bordas, antes da interface completa. Imagem preta impede avançar com esse motor. |
| Recorte e glow juntos | Demonstrar miniatura viva + halo RGBA externo sem fundo opaco, vazamento ou clipping. |
| DPI misto | Comparar quadrado e lupa em 100%, 125%, 150% e 200%, inclusive origem/destino em monitores diferentes. |
| Foco e edição | Alt+Tab não deixa conteúdo ou glow; seleção não rouba foco nem clica no jogo. Nenhuma exceção permanente para o painel. |
| Layout do Tibia | Movimentar cliente preserva origem relativa; mudança incompatível pausa e permite reposicionar. |
| Vários personagens/clientes | Vincular HWND correto e trocar perfil sem um frame residual do personagem anterior. |
| Recursos e desempenho | Reutilizar thumbnails, cachear glow e liberar handles/GDI ao excluir, trocar perfil ou fechar. Medir 1, 5 e 20 mirrors. |
| Persistência | Testar isolamento, restauração e recuperação com arquivos temporários; nenhum dado pessoal em distribuição. |

## Etapas de execução propostas

1. Prova técnica descartável: uma miniatura DWM 32 × 32, lupa, camada de glow e foco estrito no Tibia real. Testar compatibilidade e DPI. Esta etapa resolve o maior risco antes de expandir o código.
2. Modelo/persistência: perfis por personagem, dados privados, validação, gravação atômica e restauração.
3. Seletores: quadrado padrão, ajuste opcional, arrasto manual, lupa, confirmação e cancelamento. Teste de foco e prevenção de cliques no cliente.
4. Motor: vários recortes, posicionamento, trava, escala/opacidade, nome opcional, glow e encerramento correto.
5. Interface: seção Mirror, controles de perfil e recorte, eventos de personagem e mensagens de estados pausados.
6. Validação: testes de modelo/isolamento, transformações de coordenadas, foco/ciclo de vida e QA nativo de captura, troca de monitor, edição e três níveis de glow.
7. Entrega de aplicativo: publicar automaticamente Beta oficial em develop por cópia temporária, preservar checkout compartilhado e mudanças dos demais agentes; confirmar pipeline, instalador e portátil disponíveis, informar versão e link. Main/estável somente após aprovação do usuário conforme AGENTS.md e docs/pipeline-beta.md.

Este pedido entrega análise e plano. Não houve mudança no aplicativo; portanto não há uma nova Beta para publicar nesta etapa.

## Critérios de aceite da futura Beta

- Quadrado inicia em 32 × 32; nenhuma calibração obrigatória; conteúdo e moldura não se confundem.
- Os dois modos têm lupa ao lado, que permanece no monitor e não cobre a seleção.
- Cor livre e glow mínimo/médio/máximo funcionam nos dois modos, são visualmente distintos e persistem.
- Ao trocar aplicativo, minimizar ou fechar Tibia, imagem, título, lupa e glow desaparecem; ao voltar, restaura somente o estado válido do perfil.
- Dois personagens com três perfis cada mantêm regiões/aparências isoladas após reiniciar.
- Aumentar a escala do mirror não altera a região de origem.
- Trocar monitor/DPI não desloca a origem nem deixa o destino fora da tela; layout incompatível solicita reposicionamento em vez de mostrar a região errada.
- Nenhum clique interceptado quando travado, nenhuma ativação indevida e nenhum handle residual após excluir/trocar/encerrar.
- Compatibilidade e custo medidos no cliente real; limites de modos gráficos documentados com evidência.

## Fontes técnicas

- Microsoft, DwmUpdateThumbnailProperties: https://learn.microsoft.com/windows/win32/api/dwmapi/nf-dwmapi-dwmupdatethumbnailproperties
- Microsoft, High DPI Desktop Application Development: https://learn.microsoft.com/en-us/windows/win32/hidpi/high-dpi-desktop-application-development-on-windows
- Skill utilizada: C:\Users\Zandao\.codex\.tmp\plugins\plugins\superpowers\skills\brainstorming\SKILL.md
- Análise anterior relevante: docs/analise-timers-tibiavision.md.
