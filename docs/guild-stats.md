# Integração Guild Stats

A nova aba usa exclusivamente páginas públicas do GuildStats.eu. O cadastro de personagens já existente continua sendo gerenciado pelo módulo personagens.py.

## Fonte e comportamento

- Perfil: https://guildstats.eu/character/Zandao (o nome é codificado na URL).
- Abas: https://guildstats.eu/include/character/tab.php?nick=Zandao&tab=experience
- Abas públicas consultadas sob demanda: character, experience, deaths, timeonline, highscore, insomnia e drome.
- Mortes: part=table&page=N para navegar pelos registros.
- Histórico detalhado: o site exige verificação de navegador; a aba informa isso e permite abrir a página original.
- Não existe uma API JSON documentada usada aqui. O adaptador lê tabelas HTML e retorna texto estruturado. Nenhum HTML ou JavaScript remoto é executado no aplicativo.

O próprio site informa que coleta XP do tibia.com para o top 1000 por vocação no mundo. Esta integração consulta o GuildStats, sem consultar o tibia.com para os dados dessa aba. A perda nas mortes é estimada pelo site considerando promoção e todas as blessings.

XP diária usa a variação publicada pelo site, inclusive valores negativos. Ontem e anteontem usam datas de calendário local exatas; ausência de registro não é zero. O último registro e a atualização na fonte aparecem separadamente. Na consulta real de 12/10/2026, a experiência mais recente era de 10/10/2026, atualizada na fonte em 11/10/2026.

Os totais mensais somam somente as datas públicas retornadas e exibem cobertura e lacunas. Não equivalem necessariamente ao mês completo; o site reserva histórico mais longo para doadores.

O hover sempre acompanha o personagem em uso. Buscar outro nome altera apenas a consulta. Trocar o personagem em uso restaura o acompanhamento automático. Respostas antigas são descartadas para não substituir uma busca mais recente.

Cache em memória por personagem, aba e página, com validade de 15 minutos. Atualizar força uma nova consulta. Falha de rede conserva o cache anterior e o identifica como desatualizado. O cache não altera os arquivos pessoais.

## Validação

236 testes Python passaram, incluindo seis testes específicos do adaptador. Interface validada no Chrome em 1320×840 e 400×800; busca independente, mudança do personagem e escape dos dados passaram sem erros JavaScript. Consulta pública real de XP e segunda página de mortes confirmadas.

Arquivos: guild_stats.py, web/guild_stats.js, web/index.html, web_api.py e test_guild_stats.py. Não foi criada uma aplicação nova.
