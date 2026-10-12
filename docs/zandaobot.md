# ZandaoBot

Painel diário do ZandaoTools, independente do Discord e da assinatura do NabBot.

## Uso

Abra ZandaoBot no menu. O padrão é o mundo do personagem escolhido em Usar. Pesquisar um mundo não muda o personagem nem seus dados. Personagem em uso volta ao acompanhamento automático. Uma consulta independente permanece no mundo pesquisado ao trocar de personagem.

## Fontes e comportamento

- Rashid e server save: tibia_info, com virada às 10h de Berlim e horário de verão europeu.
- Criatura e boss boostados: TibiaData, cache diário existente e aviso quando atrasado ou sem conexão.
- Mundo e sugestões: TibiaData /v4/world/{nome} e /v4/worlds. Cache separado por mundo; consulta anterior identificada após falha.
- Dream Court: API pública MediaWiki de TibiaWiki, lendo Template:Dream Scar Boss/Offsets e Template:Dream Scar Boss com data da revisão. Calcula a previsão pelo dia do Tibia e pelo ajuste específico do mundo. O boss é identificado como previsto: server saves extras podem deslocar a rotação. Mundos marcados Uncertain na Wiki recebem aviso; mundo sem regra retorna indisponível. Alterações não reconhecidas da fórmula falham em vez de executar código remoto ou aplicar uma regra antiga.
- Yasir: TibiaTrade /trpc/world.list resolve o mundo; /trpc/miniWorldChange.listActive consulta as mudanças ativas daquele mundo. Oriental Trader identifica presença. Ausência só é exibida para resposta válida, com lista completa recebida. Cidade não é fornecida pela fonte: o painel informa isso e sugere verificar Carlin, Ankrahmun ou Liberty Bay. A fonte não expõe horário de coleta no jogo; o horário mostrado é o da consulta do aplicativo.
- Outras Mini World Changes: nomes das mudanças ativas do mundo consultado.
- Calendário: TibiaCalendar publica um bundle compacto em seu CDN e /api/trpc/events.listDelta fornece alterações ao vivo. O app obtém os metadados da página e mescla o delta por id; falha no delta não apresenta o snapshot antigo como atual. Notícias são excluídas do calendário. Eventos ativos e próximos 60 dias têm início, fim e abrangência explícita. Eventos de server save terminam no SS da data final (limite exclusivo). Eventos de outros mundos não aparecem no mundo pesquisado.
- Avisos específicos do mundo: TibiaData /v4/news/newsticker, filtrado pelo nome completo do mundo. Eventos de compensação podem estar somente em notícias; a ausência no calendário não prova ausência de evento específico.
- Últimos anúncios: publicações community de /v4/news/latest, separadas do calendário. world_quest_titles é histórico de conquistas e nunca é tratado como evento ativo.

Fontes: https://docs.tibiadata.com/ ; https://tibia.fandom.com/wiki/Dream_Scar/Boss_of_the_Day ; https://tibiatrade.gg/mini-world-changes ; https://tibiacalendar.com/en/calendar . Regras da TibiaWiki: conteúdo CC BY-SA, fonte/revisão identificadas no painel. Nenhum script remoto, token, credencial ou dado premium é usado.

## Cache e falhas

Cache em memória: mundo e Mini World Changes por cinco minutos; lista de mundos, regras Dream Court e calendário por uma hora; anúncios por quinze minutos. Atualizar força nova consulta. Mini World Changes expiram também no server save. Falhas preservam o timestamp anterior e mostram dados anteriores; nunca convertem falha em Yasir ausente. Uma consulta que cruza o server save não é atribuída ao novo dia como confirmada.

## Integração e validação

Arquivos: zandaobot.py, zandaobot_sources.py, web/zandaobot.js e web/zandaobot.css. Integração em web_api.py e web/index.html. Bibliotecas padrão do Python; o empacotamento existente inclui os imports e a pasta web.

Testes: python -m unittest test_zandaobot test_zandaobot_sources test_web_scripts. Cobrem fontes inválidas, cache anterior, virada do dia, regras por mundo, fim exclusivo, escopo, delta e personagem padrão. JavaScript validado com node --check. Layout renderizado em 1100px e 380px com dados públicos reais de Rasteibra, sem overflow.

Consultas públicas em 12/10/2026: Rasteibra retornou Izcandar the Banished previsto e Yasir ausente na consulta; Lobera teve Oriental Trader ativo; Antica retornou Malofur Mangrinder previsto e Yasir ausente. Orcsoberfest (09→16/10) e Full Moon (12→15/10) estavam ativos. Esses exemplos são históricos da validação, não valores fixos do aplicativo.

A publicação Beta usa cópia temporária de develop conforme docs/pipeline-beta.md, sem trocar a branch compartilhada nem levar outras alterações pendentes. A versão estável permanece inalterada.

Validação final antes da publicação: 302 testes passaram em cópia limpa de develop com as dependências do projeto. Testes de navegador confirmaram busca por mundo, personagem padrão, descarte de respostas atrasadas e escape de texto remoto.
