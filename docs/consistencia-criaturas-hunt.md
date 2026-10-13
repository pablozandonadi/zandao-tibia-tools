# Comparação entre Hunt Analyser e Criaturas da hunt

As imagens enviadas comparam entradas distintas: Hunt Analyser tem 415 abates de oito nomes, enquanto a composição manual tem apenas Draken Warmaster (126) e Draken Spellweaver (80). A lista original possui 86 Draken Spellweavers, além de outros monstros. Portanto não representa a mesma composição.

Também são métricas distintas: 57,3% físico vem do Received Damage; 68,2% fogo é um perfil estimado das faixas de ataques da Wiki. A Wiki não informa a frequência com que o monstro usa cada ataque. Melee, posicionamento e proteções mudam o dano efetivamente recebido; não é correto ajustar artificialmente a estimativa para coincidir com uma sessão.

## Correção

- Em Criaturas da hunt, “Usar esta hunt” carrega os textos de Hunting Analyser e Received Damage da mesma entrada do histórico, somente para leitura.
- Colar Hunting Analyser seguido de Received Damage também detecta automaticamente o dano. Importar outra composição limpa o Received Damage anterior se o novo log não o possui, evitando misturar sessões.
- A tela informa abates incluídos / abates originais e os nomes omitidos por falta de GIF. No exemplo, seis criaturas reconhecidas somam 408 dos 415 abates; Lizard Magistratus e Lizard Noble somam os sete omitidos.
- O dano medido usa diretamente o cálculo existente em `damage_core.analisar`, inclusive seus critérios de percentuais e arredondamento. O Hunt Analyser não foi modificado.
- A resistência média usa a mesma ponderação de abates + Damage Sources quando as fontes correspondem às criaturas. A composição continua exibindo o percentual dos abates, que é uma medida distinta do peso para atacar.
- Sem Received Damage, um aviso deixa explícito que o perfil da Wiki não é a distribuição real da hunt. Máximos de golpes continuam vindo da Wiki, mesmo no modo medido.

Dados das fichas ainda podem diferir porque o planejador consulta as Wikis BR/EN e mostra divergências entre elas. Reutilizar a mesma ponderação não torna bases de resistência diferentes idênticas. Quando há Mana Drain, ele continua separado visualmente; os percentuais medidos seguem o cálculo do Hunt Analyser em relação ao dano recebido.

## Validação

Teste da composição das imagens com 415 abates, 408 incluídos, seis criaturas e 86 Draken Spellweavers; importação conjunta do dano; equivalência dos percentuais e pesos com damage_core; leitura do histórico sem salvar; limpeza de dano ausente entre sessões; QA visual e de importação em navegador. Publicação somente na Beta oficial em develop.
