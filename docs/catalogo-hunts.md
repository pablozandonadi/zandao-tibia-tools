# Catálogo de locais e sessões públicas

A seção **Criaturas da hunt > Locais de hunt** é opcional. A busca manual continua disponível para uma única criatura. Hunt Analyser e Input Analyser preservam seus fluxos existentes.

O usuário pode buscar nome, região ou apelido, escolher o local/piso e filtrar contexto e período. Há três formas de carregar uma composição:

- Wiki: criaturas documentadas, pesos iguais ajustáveis. Bosses/condições explicitamente separados nas fontes não entram automaticamente.
- Observada: média da participação dos abates por sessão confirmada, sem favorecer sessões mais longas. Não determina quantidade de um respawn/pull.
- Sessão pública: quantidades exatas daquela sessão e um Input real disponível. Parties com Input parcial têm aviso; não é inferido dano dos membros ausentes.

O painel de locais mostra o perfil público observado. Os gráficos de ataques abaixo continuam sendo estimativas da Wiki, exceto quando um Input real é selecionado/colado. A origem aparece na análise. Dados públicos refletem proteções, posição e comportamento dos jogadores. Não representam dano bruto nem uma previsão exata para outro personagem.

## Coleta e correlação

`hunt_catalog_collect.py` usa as APIs públicas BR/EN e páginas públicas de hunt-analyser.com, com rate limit, tentativas limitadas e checkpoints. Não resolve desafios de acesso; registra indisponibilidades. O parser extrai listas explícitas de criaturas e setores, sem transformar menções narrativas em respawns.

Uma sessão é confirmada quando título/apelido e composição são compatíveis (pelo menos 80% dos abates), ou quando uma composição sem título reconhecido corresponde a um único local principal com pelo menos duas criaturas e 95% de cobertura. Pisos semelhantes, títulos contraditórios e rotas sem correspondência ficam pendentes; não entram nos perfis.

Para atribuir Input ao local, pelo menos 80% das fontes de dano devem ser criaturas documentadas ali. Sem tabela de fontes, exige-se pelo menos 95% de cobertura dos abates. A média é por registro de Input, com intervalo interquartil e contagem de amostras. Registros vinculados identificáveis são deduplicados pelo ID de origem e ordinal. Mana mantém o denominador original do Input e é identificada separadamente do HP. As tabelas de tipos/fontes são marginais: não existe cruzamento individual monstro × elemento disponível para inferir automaticamente.

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
