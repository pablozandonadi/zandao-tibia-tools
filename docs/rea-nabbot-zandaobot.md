# Investigação NabBot e fontes do ZandaoBot — 12/10/2026

## Documentação indicada pelo usuário

- https://docs.nabbot.xyz/premium/#benefits : benefícios Premium, incluindo Daily Status.
- https://docs.nabbot.xyz/premium/daily_status/ : Rashid, boostados, eventos, Tibiadrome e Dream Court. A lista atual não documenta Yasir.
- https://docs.nabbot.xyz/commands/watchlists/#watchlist-edit : edição de listas de personagens/guildas, contagem de online, links e tempo online. Não documenta o serviço diário ou suas fontes.
- https://docs.nabbot.xyz/changelog/#version-5110-2025-09-23 : registra correção da rotação da Dream Court, que estava um dia atrasada. Demonstra uso de rotação, sem revelar fórmula, ajustes por mundo ou fonte.

## Escopo e limites do REA

REA capture_browser_scenario observou a home pública do NabBot (HTTP 200), 19 scripts JavaScript e a consulta pública https://api.nabbot.xyz/servers/count. Durante essa captura da home não houve requisição de Dream Court, Yasir ou Daily Status. Essa observação não cobre o painel autenticado nem o backend do bot no Discord.

A captura retornou cleanup_incomplete; scripts e requisições foram retidos, mas sem um envelope de Evidence de sucesso para o cenário completo. A análise estática focada retornou provider_timeout com Evidence parcial ev_277da22ade393375a36af444139256ac9448a68280b2ae3f2e3484f7e83d60d8; summary ev_5e408b487a6e2c8db67cf6423a85a540bf3122b15be166faa060790d47ce3f03, na sessão de investigação. Essas limitações impedem afirmar que o código premium foi decompilado ou que conhecemos a API privada.

O repositório público https://github.com/Galarzaa90/NabBot foi arquivado em 2019, antes do Daily Status documentado em 2025; não estabelece a implementação premium atual. Nenhuma API pública do NabBot para Dream Court/Yasir foi estabelecida neste escopo.

## Implementação independente validada

Dream Court: regras por mundo da TibiaWiki, com validação integral da fórmula, mais conferência online usando action=expandtemplates e {{Dream Scar Boss|{{Dream Scar Boss/Offsets|MUNDO}}}}. Caso a resposta expandida divirja do cálculo, o app mostra consulta divergente. A resposta continua sendo uma rotação publicada, sujeita a server saves extras e ajustes da Wiki; não é observação direta dentro do jogo.

Yasir: consulta de Mini World Changes do mundo e lista de mundos com Oriental Trader no TibiaTrade. O catálogo resolve o id do Oriental Trader. Ambas são rotas da mesma fonte, não fontes independentes. Resultados divergentes não confirmam ausência. Há fallback para uma resposta válida quando a outra falha, preservação de cache e identificação de dados anteriores. A fonte não informa cidade ou horário de coleta no jogo.

Validação real: em 12/10/2026, Rasteibra retornou Izcandar the Banished na expansão da Wiki; as duas consultas TibiaTrade concordaram que Yasir não estava listado em Rasteibra. Yasir estava listado em Lobera, Luminera, Luzibra, Monza, Premia, Refugia, Sonira, Stralis, Xybra e Yubra. São exemplos históricos, não valores fixos.

## GIFs e layout

GIFs de Rashid, Yasir e cinco bosses Dream Court obtidos pelo espelho público TibiaWiki BR: oito frames cada, 64×64. Origem registrada em web/assets/zandaobot/fontes.json. Boostados usam os GIFs oficiais retornados pelo TibiaData; URLs aceitas restritas ao CDN oficial. Falha de imagem mostra ícone, sem quebrar o card.

O painel usa cards próprios para evitar as margens e sombras globais que desalinhavam a grade. Informações globais na primeira linha, Dream Court/Yasir na segunda, status/server save compactos e metadados recolhidos. A lista de mundos com Yasir permite consulta rápida sem mudar o personagem ativo.

Validação: 325 testes passaram na cópia sincronizada de develop. Testes de navegador carregaram cinco GIFs e verificaram 1400/1100/850/380/320px, seleção de mundo, personagem padrão, respostas atrasadas e escape de texto/URL. Nenhuma confirmação dentro do jogo ou comparação com mensagem Premium foi realizada, pois o usuário não tem acesso ao serviço Premium.
