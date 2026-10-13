# Integração Guild Stats

A nova aba usa exclusivamente páginas públicas do GuildStats.eu. O cadastro de personagens já existente continua sendo gerenciado pelo módulo personagens.py.

## Fonte e comportamento

- Perfil: https://guildstats.eu/character/Zandao (o nome é codificado na URL).
- Abas: https://guildstats.eu/include/character/tab.php?nick=Zandao&tab=experience
- Abas públicas consultadas sob demanda: character, experience, deaths, timeonline, highscore, insomnia e drome.
- Mortes: part=table&page=N para navegar pelos registros.
- Histórico detalhado: quando o site exige verificação, a consulta abre a janela interna do aplicativo para o usuário concluí-la.
- Não existe uma API JSON documentada usada aqui. O adaptador lê tabelas HTML e retorna texto estruturado. A tela de resultados recebe apenas texto estruturado e escapado. A página remota e seus scripts ficam restritos à janela de verificação, sem API Python do aplicativo.

O próprio site informa que coleta XP do tibia.com para o top 1000 por vocação no mundo. Esta integração consulta o GuildStats, sem consultar o tibia.com para os dados dessa aba. A perda nas mortes é estimada pelo site considerando promoção e todas as blessings.

XP diária usa a variação publicada pelo site, inclusive valores negativos. Ontem e anteontem usam datas de calendário local exatas; ausência de registro não é zero. O último registro e a atualização na fonte aparecem separadamente. Na consulta real de 12/10/2026, a experiência mais recente era de 10/10/2026, atualizada na fonte em 11/10/2026.

Os totais mensais somam somente as datas públicas retornadas e exibem cobertura e lacunas. Não equivalem necessariamente ao mês completo; o site reserva histórico mais longo para doadores.

O hover sempre acompanha o personagem em uso. Buscar outro nome altera apenas a consulta. Trocar o personagem em uso restaura o acompanhamento automático. Respostas antigas são descartadas para não substituir uma busca mais recente.

Cache em memória e disco por personagem, aba e página, com validade de 15 minutos e até 128 consultas persistidas. Atualizar força uma nova consulta. Falha de rede conserva o cache anterior e o identifica como desatualizado. O cache não altera os arquivos pessoais.

## Validação

236 testes Python passaram, incluindo seis testes específicos do adaptador. Interface validada no Chrome em 1320×840 e 400×800; busca independente, mudança do personagem e escape dos dados passaram sem erros JavaScript. Consulta pública real de XP e segunda página de mortes confirmadas.

Arquivos: guild_stats.py, web/guild_stats.js, web/index.html, web_api.py e test_guild_stats.py. Não foi criada uma aplicação nova.

## Consulta interna e continuidade (13/10/2026)

HTTP 403/desafio Cloudflare abre uma janela WebView do aplicativo quando a consulta foi iniciada pelo usuário. O usuário conclui a verificação nessa janela; o adaptador lê o HTML no mesmo contexto, sem copiar cookies ao Python. A janela não recebe js_api nem funções privilegiadas. Hover nunca cria janela e aguarda pelo menos 60 segundos entre falhas. A janela é ocultada após os dados serem reconhecidos; cancelamento e timeout de dois minutos preservam os dados anteriores.

Sessão WebView persistida em webview_session e consultas em cache_guild_stats dentro do diretório de dados do canal. Pastas privadas ignoradas pelo Git e não incluídas nos recursos distribuídos. Cache limitado às 128 consultas recentes; gravação atômica e tolerante a corrupção/falta de acesso. Data original permanece visível no fallback. Sem consulta anterior não se inventam dados. O Cloudflare pode rejeitar WebViews: verificação interna é uma tentativa compatível com a preferência do usuário, não garantia de acesso.

O botão Verificar acesso no app substitui Abrir no site. Não há lançamento de navegador externo pelo fluxo GuildStats. Testes cobrem persistência, HTTP 403, cancelamento, cache corrompido e espera após falhas. Validação interativa do desafio real depende de aceitação do WebView2 pelo site.

Validação local: 416 testes passaram com dependências fixadas; JavaScript e diff sem erros. WebView2 real carregou o desafio do GuildStats e confirmou API remota vazia. O desafio humano não foi concluído nessa checagem; não se afirma acesso real aos dados após verificação.

### Beta oficial entregue

Beta 1.0.23-beta.39.1: https://github.com/pablozandonadi/zandao-tibia-tools/releases/tag/v1.0.23-beta.39.1
Pipeline: https://github.com/pablozandonadi/zandao-tibia-tools/actions/runs/38472970563
Código: e057b9a8be10b4da174960ade8ef86c25bf6c920. Pipeline concluído com sucesso; 417 testes passaram. Instalador (23.831.737 bytes), portátil (30.561.876 bytes), SHA256SUMS.txt, package-manifest.json e sbom.json confirmados disponíveis.

A develop incorporou a estável 1.0.23 já publicada (7f3865c), mantendo a main como ancestral; main não foi modificada por esta entrega. Checkout compartilhado permaneceu na branch original. Somente mudanças deste fluxo foram publicadas por cópia temporária.

Teste pendente pelo usuário na Beta: concluir o desafio real do GuildStats na janela interna e confirmar retorno dos dados. A WebView real carregou o desafio; sua aceitação após interação humana ainda não foi comprovada. Cache permite continuidade apenas após uma consulta válida.
