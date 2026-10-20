# News na Home

O card **Eventos do Tibia** mantém os anúncios da categoria `community`. O card
**News** mostra os demais artigos de `/news/latest`, incluindo `development`
(como “Balancing, Fixes and Changes”). O calendário continua independente.

News ocupa a largura inteira acima do calendário e dos Eventos do Tibia. Abaixo,
calendário à esquerda e Eventos do Tibia à direita mantêm o layout anterior
(uma coluna em telas estreitas).

**News Ticker** fica no topo: lista vertical compacta com data, prévia em uma
linha e seta. Cada aviso abre individualmente para mostrar o texto recebido e
o link oficial. Os cinco mais recentes aparecem inicialmente; os outros cinco
ficam em **Mais avisos**, recolhido por padrão. Não há colunas nem agrupamentos
por dia. Em seguida, a notícia
principal mais recente fica visível com imagem, título e data. As sete anteriores
ficam em **Notícias anteriores**, recolhidas inicialmente, numa lista vertical.
O estado de cada aviso e do arquivo é preservado durante a sessão, inclusive nas
atualizações da Home. Sem artigos, os avisos continuam disponíveis e a ausência
de notícia principal é informada.

São até oito artigos por card e dez avisos gerais, sem IDs repetidos. Os avisos
têm trecho de até 400 caracteres e link para o texto oficial. A interface usa
apenas texto escapado; não insere HTML remoto. Imagens continuam limitadas à
origem oficial já permitida e têm fallback quando falham.

Os caches existentes são reutilizados: artigos por 15 minutos, avisos por cinco
minutos e imagens dos detalhes por seis horas. Falhas preservam os dados anteriores
e mostram a data de consulta separadamente para artigos e avisos. Os avisos
específicos de mundo e a extração de compensações continuam independentes.

Validação local: 35 testes de `test_zandaobot`/`test_zandaobot_sources`, oito de
`test_world_board` e teste Chrome de `test_zandaobot_ui.cjs` em 1400, 1000 e 320 px.
Não são necessárias OpenAI, novas fontes nem consultas extras de detalhe dos avisos.
