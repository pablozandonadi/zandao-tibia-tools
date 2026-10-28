# TibiaRise como fonte adicional de XP

O usuário pediu usar os parâmetros públicos do TibiaRise para recuperar dados de XP enquanto a consulta direta ao GuildStats está bloqueada. A fonte é identificada como TibiaRise: a integração não pressupõe equivalência nem atribui suas medições ao GuildStats.

## Contratos e limites

- Personagens: GET `/api/character/{nome}?page=1` e, quando indicado, página 2. Somente nome/mundo, data, level, XP total e ganho são aproveitados. Até 60 registros; são necessárias 31 medições consecutivas para calcular 30 intervalos.
- Rankings: GET `/api/experience-by-world/{mundo}/daily`, `weekly`, `monthly`. Preservar `period.startDate`, `endDate` e `updatedAt`; a lista pública é limitada a 100 entradas. Nomes duplicados são omitidos sem escolher nem somar ganhos ambíguos.
- Trata-se da API pública utilizada pelo frontend, sem garantia de estabilidade ou cobertura. Não há login, chave, proxy nem tentativa de resolver bloqueios.

## Coleta e apresentação

Os comandos continuam sem HTTP para XP. A consulta enfileira nome/mundo em uma fila de até 200 personagens; o coletor existente busca no máximo um personagem e um mundo por execução, com lease persistente. Após a primeira solicitação, uma próxima consulta poderá aproveitar o cache. Sucesso aguarda seis horas; falha aguarda quinze minutos. Só solicitações dos últimos sete dias são atualizadas e registros sem solicitações por sessenta dias são removidos.

O cache é cifrado em tabela separada e não altera o histórico GuildStats ou medições TibiaData. Preferência: GuildStats válido, TibiaRise válido, TibiaData; dados antigos permanecem datados e não permitem projeção. Ganhos negativos e zero são válidos. Lacunas, registros duplicados, mudanças de nome/mundo e incoerência entre XP ganho e total impedem inventar intervalos completos.

Os comandos mostram “Último intervalo” e “7/30 intervalos diários”, com horários UTC reais e fonte. Projeções precisam de períodos completos, recentes e comparáveis. A legenda diária inclui TR; modelos customizados recebem os valores antigos de ontem/GuildStats vazios para medições de outra fonte.

Sem mudanças na agenda, sessão WhatsApp, autenticação, Mensagem do dia manual ou World Board. Validação offline com contratos sintéticos; teste operacional somente de leitura pública, sem envio real.
