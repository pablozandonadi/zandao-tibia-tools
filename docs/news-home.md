# News na Home

O card **Eventos do Tibia** mantém os anúncios da categoria `community`. O card
**News** mostra os demais artigos de `/news/latest`, incluindo `development`
(como “Balancing, Fixes and Changes”). O calendário continua independente.

News ocupa a largura inteira acima do calendário e dos Eventos do Tibia. Os dias
se distribuem em três colunas em telas largas, duas em telas médias e uma em
telas compactas. Abaixo, calendário à esquerda e Eventos do Tibia à direita
mantêm o layout anterior (uma coluna em telas estreitas).

News agrupa por dia: artigos com imagem ficam visíveis; os avisos menores de
`/news/newsticker` ficam em **News Ticker**, expansível abaixo dos artigos do dia.
Dias que têm apenas avisos também aparecem. O estado aberto/fechado é preservado
nas atualizações da Home durante a sessão.

São até oito artigos por card e dez avisos gerais, sem IDs repetidos. Os avisos
têm trecho de até 400 caracteres e link para o texto oficial. A interface usa
apenas texto escapado; não insere HTML remoto. Imagens continuam limitadas à
origem oficial já permitida e têm fallback quando falham.

Os caches existentes são reutilizados: artigos por 15 minutos, avisos por cinco
minutos e imagens dos detalhes por seis horas. Falhas preservam os dados anteriores
e mostram a data de consulta separadamente para artigos e avisos. Os avisos
específicos de mundo e a extração de compensações continuam independentes.

Validação local: 35 testes de `test_zandaobot`/`test_zandaobot_sources`, oito de
`test_world_board` e teste Chrome de `test_zandaobot_ui.cjs` em 1400 e 320 px.
Não são necessárias OpenAI, novas fontes nem consultas extras de detalhe dos avisos.
