# Task Itens Analyser — análise e implementação

Referência: https://tibiacacau.com.br/weekly-tasks/ e https://tibiacacau.com.br/weekly-tasks/session-analyser. Inspeção em 12/10/2026.

## O que foi verificado

O frontend público usa Angular, Angular Material e Webpack, com módulos carregados por rota. O menu Weekly Tasks tem uma lista de itens e um Session Analyser. A lista permite pesquisa paginada, filtro Yasir, imagens, NPC/preço e seleção de itens lembrada em localStorage. A lógica relevante está nos bundles reference-weekly.js e reference-session.js; o roteamento está em reference-main.js e o mapa de chunks em reference-runtime.js.

O parser processa ao clicar e automaticamente 100 ms após colar. Separa Killed Monsters e Looted Items pelas posições dos cabeçalhos; usa linhas de quantidade e nome. Extrai duração e período. Envia somente nomes de monstros e itens para POST /api/tasks/analyze-session. As quantidades ficam no frontend. Limpar elimina texto e resultados. Os cards mostram nome, imagem quando disponível, quantidade, divisão e, nas tasks, NPC/preço unitário.

O Session Analyser observado mostra duas categorias: weekly task e outros drops. Não encontrei separação de embuimentos nem handler de cópia nos templates desses cards. A cópia por clique é requisito desta implementação. Teste real no Chrome com 13x werewolf fur e 25x rope belts retornou Werewolf Fur como task (Yasir, 380 gold) e Rope Belts como outro drop.

A divisão original começa em 4 pessoas, é lembrada em localStorage e sanitiza para inteiro positivo. Usa max(1, floor(quantidade / pessoas)) para qualquer quantidade positiva. Exemplo: 1 item / 4 pessoas aparece como 1 cada. O novo menu conserva a quantidade: 0 por pessoa, sobra 1.

O GET /api/items?page=0&size=2000 retornou 450 itens, todos com isWeeklyTask=true, nomes, imagens, fontes de drop, NPC, preço, raridade e ID. GET /api/tasks retornou uma lista vazia. Uma chamada de exemplo ao POST sem monstros retornou HTTP 400; não extrapolei isso como regra interna do servidor. O código privado do backend, banco de dados, algoritmos de correspondência e manutenção do catálogo não estão acessíveis nesta análise.

REA analisou os três primeiros bundles sem falhas de parsing (67 módulos), evidência ev_2a8ffb6e69d3ef37eb644c71a4e0051109933ba4432d977b8115de82bfff1712. A cobertura do grafo semântico foi parcial por limite de recursos. A análise estática não comprova execução de todos os módulos; o cenário no Chrome confirma apenas o fluxo de exemplo descrito acima. O bundle adicional do parser foi lido diretamente depois.

## Comportamento implementado

Menu Task Itens Analyser, no estilo visual do aplicativo. Colar dispara análise; Processar dados permite repetir; Limpar cancela resultados pendentes e limpa o texto. Aceita Hunting Analyser completo ou linhas de loot. Ignora abates em sessões completas, agrega duplicatas, reconhece artigos e plurais comuns/aliases dos embuimentos. Nomes sem correspondência ficam visíveis em outros drops.

Classificação em três categorias: tasks pelo catálogo público salvo em data/task_items.json, embuimentos pela base existente data/imbuements.json e outros itens. A classificação não envia o texto ao site. Um item que constar nas duas bases permanece em tasks com indicação do embuimento. No snapshot atual não há nomes canônicos compartilhados entre as duas bases.

Clique simples ou Enter/Espaço no card copia somente o nome via clipboard nativo já usado pelo app. Selecionar texto não aciona a cópia automática. O texto permanece selecionável com Ctrl+C. Os valores de NPC são unitários e não representam cotação de market. A divisão mostra quantidade por pessoa e sobra, inclusive quando há menos itens que pessoas. A entrada de pessoas aceita inteiros de 1 a 1000.

O catálogo é um snapshot de 12/10/2026, sem atualização automática. Embuimentos usam os materiais já cadastrados no projeto. As imagens das tasks são carregadas por HTTPS do site e requerem internet; falhas ocultam apenas a imagem. Itens fora do catálogo continuam sendo classificados sem imagem. O instalador inclui o novo JSON; o executável existente ainda precisa ser recompilado para conter as mudanças.

## Validação

10 testes Python (8 do parser/classificação e 2 existentes de integridade dos scripts), compilação Python, sintaxe JavaScript e git diff --check passaram. O teste de navegador executou o script real do novo menu com uma API de exemplo: clique copia o nome, Enter copia, texto selecionado não é sobrescrito, Limpar remove cards e viewport de 390 px não tem overflow horizontal. A prévia está em preview.png. Não foi executado o aplicativo PyWebView completo nem gerado novo EXE.


## Correção dos sprites em 12/10/2026

Todos os cards agora recebem uma imagem, incluindo embuimentos e outros drops. Foram empacotados 556 sprites locais em web/assets/items, com manifesto em web/assets/item_images.json, abrangendo as 450 tasks, todos os materiais cadastrados e os 38 itens do print. GIFs são mantidos como GIFs, sem converter para quadro estático; Gold Coin conserva 8 quadros. As imagens vêm da TibiaWiki, com fallback ao catálogo público para tasks.

O endpoint task_itens_imagens lê os recursos empacotados e retorna data URIs. Novos itens são resolvidos pelo nome, incluindo plurais e nomes com apóstrofos, e guardados em cache_task_images ao lado do EXE. Enquanto busca, e se não encontrar o sprite real, o card conserva uma imagem indicativa de item em vez de ficar vazio. A análise e a cópia continuam funcionando.

Validação: todos os materiais e itens do print têm sprite real offline; bytes dos GIFs preservados; 263 testes passaram. No navegador, todos os 39 cards da amostra (38 do print + Werewolf Fur) carregaram imagens reais. Clique, seleção do texto, teclado, limpeza e layout móvel permanecem funcionais.
