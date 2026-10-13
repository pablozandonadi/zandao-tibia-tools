# Plano: catálogo de hunts e perfis observados de dano

## Objetivo

Na área Criaturas da hunt, permitir escolher um local — e seu piso ou setor quando necessário — para preencher a composição e consultar os danos desse local. A pesquisa manual de uma criatura continua independente. Hunt Analyser e Input Analyser permanecem opcionais.

A base terá três camadas distintas: cadastro e criaturas das Wikis; composição observada nas sessões públicas; dano recebido observado nas sessões que disponibilizam Input Damage. Não transformar estimativas de ataques da Wiki em dano recebido medido.

## O que foi verificado nas fontes

- [Locais de Caça, Tibia Wiki BR](https://www.tibiawiki.com.br/wiki/Locais_de_Ca%C3%A7a): o índice consultado contém 501 locais, com nome, level, premium, dificuldade, vocações, área e localização. Ainda será necessário abrir as fichas dos locais para obter seus monstros e setores.
- [Hunting Places, Wiki EN](https://tibia.fandom.com/wiki/Hunting_Places): a API pública respondeu; a categoria retornou 459 páginas, incluindo o próprio índice. A contagem precisa excluir índices, listas e páginas descontinuadas antes de formar o catálogo. A coleta usará a API original, sem depender da tradução automática.
- [Sessões públicas](https://www.hunt-analyser.com/hunt_sessions?hunt_sessions_by=is_public): o índice informa mais de quatro mil sessões e fornece paginação e identificadores estáveis.
- Nas sessões [Warzone 3](https://www.hunt-analyser.com/hunt_sessions/59353), [Soulwar — Crater](https://www.hunt-analyser.com/hunt_sessions/59397) e [Falcon](https://www.hunt-analyser.com/hunt_sessions/59362), foram verificadas tabelas de monstros mortos, dano por elemento e dano por monstro. Não são apenas títulos ou resumos de XP.

Limites relevantes: dano por elemento e dano por monstro são tabelas separadas; não fornecem automaticamente uma matriz monstro × elemento. Algumas parties apresentam membros sem sessão vinculada. Uma sessão também pode incluir monstros encontrados no caminho. As inspeções acima validam a viabilidade; não representam uma coleta completa do catálogo nem das sessões públicas.

## 1. Contrato dos dados e piloto

Antes da carga completa, implementar parsers testáveis e auditar uma amostra diversificada de 20–30 sessões: solo e party, vocações diferentes, pisos distintos, sessões sem Input, rotas mistas e nomes informais.

Para cada sessão, identificar:

- ID e URL pública, data e duração, organização solo/party e contexto disponível de vocação e level.
- Contagens de monstros, indicando se o escopo é a sessão inteira ou um registro de membro.
- Quantidades e percentuais de dano por elemento; totais de dano por monstro; existência de `(other)` e dados ausentes.
- Registro de origem de cada tabela, para impedir duplicação entre uma party e sessões vinculadas ou entre vários blocos da mesma página.

Conferir somas, arredondamentos, número de linhas e eventuais limites de exibição. Ausente não significa zero. Não combinar tabelas de personagens diferentes como se fossem um único Input.

**Critério de passagem:** contagens e valores extraídos conferem com as páginas auditadas; ausência, duplicação e escopo são identificados corretamente. Guardar exemplos de teste sintéticos e um relatório de cobertura.

## 2. Catálogo completo das Wikis

Percorrer todos os locais válidos dos dois índices, com paginação, retomada e registro de falhas. Para cada local, guardar:

- ID próprio, nome canônico, nomes alternativos e fontes BR/EN, com revisão e data de consulta.
- Região, pisos/setores, requisitos e recomendações disponíveis na fonte.
- Criaturas documentadas, distinguindo spawn regular, aparições condicionais e bosses quando a fonte permitir.
- Divergências entre as Wikis e campos ainda desconhecidos.

Cruzar nomes e redirects, mantendo aliases revisados como nomes em português, inglês e apelidos usados pela comunidade. Não juntar locais diferentes só porque têm monstros semelhantes. Preservar pisos e setores como opções próprias.

O catálogo conserva todos os monstros documentados, mesmo sem GIF ou ficha completa. A interface informa o que entrou na análise; não altera os totais silenciosamente. Áreas grandes precisam de setores/pisos e de uma estratégia para o limite atual de 30 criaturas, sem cortar a lista de forma invisível.

**Critério de passagem:** relatório com locais encontrados, fichas completas, falhas de consulta, divergências e aliases pendentes. "Todos" significa todas as entradas válidas dos índices consultados, com os gaps declarados.

## 3. Coleta completa das sessões públicas

Fazer a carga inicial de todas as páginas do índice e de todos os detalhes acessíveis, com ritmo moderado, cache, tentativas limitadas, checkpoints e retomada. Não usar apenas as primeiras páginas ou os resultados populares.

Armazenar somente os campos necessários à correlação e às estatísticas. Nomes de jogadores, autores, mundos, notas livres e HTML bruto não entram nos pacotes do aplicativo. Títulos e observações podem ser usados temporariamente para identificar o local; persistir apenas o local normalizado e a evidência técnica necessária. Manter IDs/URLs públicos para rastreabilidade.

Sessões indisponíveis, privadas, incompletas ou com escopo duvidoso não entram automaticamente nas estatísticas confirmadas. Abates podem ser usados quando o Input está ausente; dano medido só entra quando existe e foi validado.

**Critério de passagem:** reconciliar IDs vistos no índice com registros coletados, falhas, duplicatas e exclusões. Disponibilizar contagem de sessões com abates e de registros com dano medido.

## 4. Correlação entre sessão e local

Usar uma hierarquia de evidências:

1. Nome canônico ou alias confirmado no título, com composição compatível.
2. Piso/setor declarado e composição compatível com aquela variante.
3. Composição de monstros suficientemente característica e sem concorrente plausível.
4. Casos ambíguos entram numa fila de revisão, com candidatos e motivos; não são forçados para o local mais parecido.

Comparar o peso dos abates, não apenas a presença de nomes. Uma criatura morta no caminho não deve dominar a classificação. "Asuras", "Rosha" ou uma rota com boss podem ser insuficientes para identificar um respawn específico. Contradição entre título e composição, múltiplos locais na mesma sessão e ausência de evidência de piso devem reduzir a confiança.

Calibrar os critérios no piloto e testar casos positivos e negativos. Uma associação incorreta contamina os perfis de dano; manter a confiança e o método de associação em cada registro. A revisão deve ser reutilizada nas próximas atualizações.

## 5. Perfis por hunt

Produzir, por local e variante:

- Número de sessões confirmadas, número de registros com Input e período coberto.
- Quantidades exatas por sessão e distribuição observada dos abates no conjunto. Uma média não será chamada de "quantidade exata do respawn".
- Perfil de dano recebido por elemento e contribuição de cada monstro, com respectivas coberturas e escopos.
- Separação por vocação e solo/party quando houver dados suficientes. Levels, equipamentos, prey, charms e posicionamento podem alterar o dano recebido; campos ausentes permanecem desconhecidos.
- Recência e mudanças de versão: usar a data da hunt, não a data da coleta. Evitar misturar automaticamente amostras anteriores e posteriores a mudanças de criaturas/respawns. Definir a janela de amostras atuais no piloto e identificar quando o perfil depende de registros antigos.
- Variabilidade entre sessões, além da média. Um registro muito longo não deve sozinho definir o "perfil típico". Usar distribuição normalizada por registro e comparar uma medida robusta com o agregado por volume de dano, identificando cada métrica.

Mana Drain continua separado visualmente e segue uma política consistente com o Hunt Analyser. Não deduzir uma distribuição monstro × elemento multiplicando as duas tabelas marginais. Máximos de golpes da Wiki ficam numa seção própria: os totais das sessões não revelam necessariamente o maior impacto individual nem a chance de um golpe fatal.

Quando faltar amostragem, mostrar "base insuficiente" e usar as Wikis como alternativa identificada. Definir os limites de amostragem depois de avaliar o piloto, sem apresentar um número arbitrário como garantia de precisão.

## 6. Interface

Adicionar um painel "Locais de hunt", com busca por nome/apelido, região e piso/setor.

Ao selecionar, mostrar fontes, criaturas, amostragem, última atualização e qualidade da correlação. O usuário poderá carregar a composição documentada pela Wiki ou a composição observada nas sessões públicas e ajustar as quantidades depois.

Apresentar três origens sem confundir os gráficos:

- **Wiki:** perfil dos ataques documentados e máximos conhecidos.
- **Sessões públicas:** perfil agregado observado naquele local, com amostragem e contexto.
- **Meu Input Analyser:** dano real da sessão colada pelo próprio usuário.

A consulta de uma criatura permanece o fluxo manual principal. Selecionar uma hunt é uma opção adicional. Não reaproveitar um Input de outra sessão ao carregar um local. Não representar um agregado público como se fosse o Input real do usuário.

## 7. Atualização periódica

Recomendo um coletor central, para não fazer cada instalação acessar milhares de páginas:

- **Diariamente:** conferir o inventário de IDs públicos e coletar detalhes novos. Verificar o índice inteiro também encontra sessões antigas tornadas públicas; olhar só a primeira página pode perdê-las.
- **Semanalmente:** revalidar o cadastro das Wikis e revisar alterações/disponibilidade das sessões conforme a estratégia de cache.
- **Periodicamente:** reconciliação completa, para detectar edições, remoções, mudanças de aliases e alterações no formato das páginas.
- **No aplicativo:** consultar a versão do snapshot a cada 24 horas, em segundo plano, além do botão "Atualizar base agora".

Cada snapshot terá versão do esquema, data, cobertura, checksums e resultado da validação. Publicação atômica: falha na coleta ou quebra de parser mantém a última base válida. Mostrar a data da base disponível, sem declarar atualização bem-sucedida quando a coleta falhou.

Separar publicação dos dados da recompilação do executável. O mecanismo será validado na Beta; a ativação no canal estável seguirá a aprovação do usuário. O agendamento de produção deve funcionar no repositório sem alterar automaticamente código ou versão da main, usando um destino próprio para snapshots de dados. Credenciais do coletor não entram no aplicativo.

## 8. Entrega e critérios finais

1. Piloto auditado e parsers aprovados.
2. Catálogo completo com cobertura e pendências explícitas.
3. Carga completa das sessões públicas, correlação e revisão dos casos ambíguos.
4. Perfis observados e painel de seleção de locais.
5. Atualização incremental central e consumo dos snapshots pelo app.
6. Testes, Beta oficial com instalador/portátil e conferência manual antes de promover a versão estável.

Testar importação sem Input, party com membros ausentes, sessões vinculadas, pisos com os mesmos monstros, rotas mistas, duplicação, exclusão, arredondamentos, atualização sem novas sessões, mudanças de HTML e rede indisponível. Também verificar que busca manual, Hunt Analyser, histórico, personagens e configurações existentes continuam funcionando e que dados pessoais não entram na publicação.

**Estado atual:** carga inicial e implementação concluídas; ver docs/catalogo-hunts.md para cobertura, políticas, validação e atualização. Casos ambíguos permanecem pendentes e fora dos perfis.
