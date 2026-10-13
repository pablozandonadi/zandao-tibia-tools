# Catálogo de locais e sessões públicas

A seção **Criaturas da hunt > Locais de hunt** é opcional. A busca manual continua disponível para uma única criatura. Hunt Analyser e Input Analyser preservam seus fluxos existentes.

O usuário pode buscar nome, região ou apelido, escolher o local/piso e filtrar contexto e período. Há três formas de carregar uma composição:

- Wiki: criaturas documentadas, pesos iguais ajustáveis. Bosses/condições explicitamente separados nas fontes não entram automaticamente.
- Observada: somente criaturas da lista regular das Wikis para o local/setor escolhido. Abates externos são excluídos antes da normalização por sessão, sem favorecer sessões mais longas. Não determina quantidade de um respawn/pull.
- Sessão pública: quantidades exatas das criaturas daquele local na sessão, preservando o total original separadamente; o Input só é aplicado quando suas fontes pertencem ao local. Parties com Input parcial têm aviso; não é inferido dano dos membros ausentes.

O painel de locais mostra o perfil público observado. Os gráficos de ataques abaixo continuam sendo estimativas da Wiki, exceto quando um Input real é selecionado/colado. A origem aparece na análise. Dados públicos refletem proteções, posição e comportamento dos jogadores. Não representam dano bruto nem uma previsão exata para outro personagem.

## Coleta e correlação

`hunt_catalog_collect.py` usa as APIs públicas BR/EN e páginas públicas de hunt-analyser.com, com rate limit, tentativas limitadas e checkpoints. Não resolve desafios de acesso; registra indisponibilidades. O parser extrai listas explícitas de criaturas e setores, sem transformar menções narrativas em respawns.

Uma sessão é confirmada quando título/apelido e composição são compatíveis (pelo menos 80% dos abates), ou quando uma composição sem título reconhecido corresponde a um único local principal com pelo menos duas criaturas e 95% de cobertura. Pisos semelhantes, títulos contraditórios e rotas sem correspondência ficam pendentes; não entram nos perfis.

Para atribuir Input ao local, todas as fontes de dano positivas devem pertencer à lista regular das Wikis daquele local/setor. Inputs com fontes externas, desconhecidas ou sem tabela de fontes ficam fora do perfil. Não se subtrai nem redistribui o dano por elemento de um log misturado, pois os dados não contêm esse cruzamento. A média é por registro de Input, com intervalo interquartil e contagem de amostras. Registros vinculados identificáveis são deduplicados pelo ID de origem e ordinal. Mana mantém o denominador original do Input e é identificada separadamente do HP. As tabelas de tipos/fontes são marginais: não existe cruzamento individual monstro × elemento disponível para inferir automaticamente.

O coletor não persiste nomes de autores/personagens, títulos livres, notas ou HTML. Nomes de criaturas não reconhecidos viram `(não catalogado)`, mantendo os totais. `hunt_catalog_publish.py` valida e publica exclusivamente o snapshot saneado e os checkpoints públicos necessários. Dados locais de histórico, personagens, timers e configurações não participam desse processo.

## Atualizações

`.github/workflows/update-hunt-catalog.yml` oferece execução manual na develop. Publica dados em `hunt-catalog-beta`, com checksum SHA-256, sem recompilar o aplicativo. Após aprovação/promoção da mudança para main, o cron diário de 08:40 UTC publica `hunt-catalog-data`. Enquanto a mudança estiver em análise na Beta, o agendamento auxiliar do Codex aciona diariamente a develop às 05:00 locais; precisa do computador ligado e do aplicativo Codex aberto. Esse auxiliar deve ser desativado quando o cron aprovado em main estiver funcionando.

A coleta verifica o inventário inteiro diariamente, coleta detalhes novos, revalida cada sessão após 30 dias e as Wikis após sete dias. `workflow_dispatch` permite forçar a revalidação. IDs removidos deixam a base somente após leitura suficiente do índice; quedas anormais de cobertura abortam a publicação.

O leitor do aplicativo consulta apenas o snapshot central, a cada 24 horas ou pelo botão Atualizar base. Valida tamanho, esquema, checksum e fontes; grava cache por substituição atômica e preserva a última base válida em falhas. Não realiza coleta de milhares de páginas no computador de cada usuário. O snapshot incluído na Beta permite consulta offline inicial.

## Validação

Testes cobrem correlação ambígua, títulos contraditórios, pisos semelhantes, listas BR/EN, abates exatos, Input parcial de party, média independente da duração, deduplicação, fontes de dano incompatíveis, saneamento, cache/checksum/fallback e limite de composição. A interface também é verificada no Chrome com Playwright: consulta manual, filtro por apelido, uso de local/sessão e descarte de Input anterior ao voltar ao modo manual.

A entrega do aplicativo ocorre apenas na Beta oficial; a versão estável aguarda aprovação do usuário. As fontes podem ter lacunas e listas antigas. A quantidade de sessões coletadas não significa que todas foram correlacionadas com segurança ou que todos os locais têm amostras suficientes.

## Carga inicial — 12/10/2026

4.467 sessões coletadas de 4.467 IDs públicos, sem falhas. 2.573 confirmadas; 1.426 ambíguas, 217 com título incompatível, 53 sem local compatível e 198 sem abates. 3.488 sessões contêm Input. Cadastro: 501 entradas no índice BR e 459 no EN; 1.527 locais/setores após extração e correlação, 1.433 com criaturas. Os demais mantêm a lacuna explícita.

## Entrega Beta

Beta oficial **1.0.21-beta.15.1**: https://github.com/pablozandonadi/zandao-tibia-tools/releases/tag/v1.0.21-beta.15.1 — instalador e portátil confirmados. Código: a03d458de4d3097946ea1bdac30608bf5de055b3. Compilação: execução 38340969643, sucesso. Coleta incremental central: execução 38340969778, sucesso. 366 testes passaram na cópia limpa de publicação; verificação da interface no Chrome também passou. O disparo manual do coletor na develop foi confirmado; a segunda execução de teste foi cancelada para evitar coleta redundante.

## Correção de delimitação — 13/10/2026

A composição agregada e o carregamento de sessões passam pelo mesmo filtro de criaturas regulares do local/setor, sem herdar a lista do pai. Os registros públicos originais ficam intactos. Os percentuais são recalculados após excluir abates externos. O leitor aplica esse filtro também em snapshots/cache antigos. Avisos compactos informam os abates e Inputs excluídos. Fire e ice library voltam a carregar cinco criaturas observadas, com elementos, picos e resistências completos. Input misturado não é aplicado como dano do local. Hunt Analyser, importação manual e consulta individual preservam seu comportamento.

Correção entregue na Beta oficial **1.0.21-beta.16.1**: https://github.com/pablozandonadi/zandao-tibia-tools/releases/tag/v1.0.21-beta.16.1. Código 5bf31d39b3bc03316c0083e961b9969906755168. 374 testes passaram; interface das duas livrarias validada com elementos, picos e resistências. Compilação 38344662400 e atualização central 38344662404 concluíram com sucesso. Instalador e portátil confirmados.

## Organização da tela — 13/10/2026

Ações no topo da composição; Hunt Analyser e Input Analyser agrupados em cards expansíveis ao lado. Busca de locais em largura inteira, com resultados clicáveis e contagem visível abaixo. Duas abas separam Local de hunt (análise de criaturas) e Hunts analisadas (dano público e composição observada). Todo o histórico é usado, sem seletor de período. O filtro por tamanho da party usa a quantidade exata de membros: solo, duo, três, quatro e cinco ou mais. Explicações, amostragem, exclusões, fontes e consulta de sessões ficam no card Informações ao fim da página, mantendo os critérios de validação existentes.

Tela reorganizada entregue na **Beta 1.0.21-beta.18.1**: https://github.com/pablozandonadi/zandao-tibia-tools/releases/tag/v1.0.21-beta.18.1. Commit d13639e94d653720d5401f2f86c1dcf3183d4496; compilação 38348172185 concluída com sucesso. Instalador e portátil confirmados. 375 testes e verificação no Chrome passaram: resultados da busca visíveis, abas separadas, histórico inteiro, filtro por membros, detalhes ao final, layout responsivo e título da hunt oculto na consulta manual.

## Alternância dos cards — 13/10/2026

As abas aparecem após escolher um local e alternam somente os dois cards de perfil de dano e composição. Resumo, elementos, picos, resistências e fichas permanecem visíveis. A composição manual é preservada/restaurada ao voltar de Hunts analisadas. O título é Perfil estimado dos ataques das criaturas do Tibia; a proveniência das Wikis permanece em Informações. Para Dragolisk, Mega Dragon e Wardragon, as revisões BR/EN consultadas não fornecem faixas de ataque: o app informa a lacuna e mostra traços, sem inventar números ou confundir ausência com zero.
