# Consulta manual de criaturas

Referência revisada: [TibiaHelper Creatures](https://tibiahelper.com/Helper/Creatures), incluindo os scripts públicos `/Scripts/creatures.js?16` e `/Scripts/creaturesJS.js?1661111`. A análise estática do JavaScript identifica `setCheckEvent` associando o clique na criatura a `selectCreature`, que adiciona a ficha e consulta a Wiki, e `removeCreature` recalculando os resultados. Não há requisito de uma sessão de hunt nesse fluxo. `updateDmgValues` trabalha com a lista de criaturas ativas.

Não foi copiado código do site para o aplicativo. As cópias usadas para inspeção ficaram em arquivos temporários. A implementação existente continua usando dados atuais das Wikis e pesos ajustáveis.

## Ajustes

- Busca e composição ficam antes dos painéis de importação.
- Adicionar uma criatura analisa automaticamente sua ficha; a quantidade inicial é 1. Sem logs nem hunt salva, uma criatura possui 100% da composição.
- Adição, remoção ou alteração manual de quantidades desativa o uso do Input anterior, para não usar o dano de uma sessão inteira como se fosse dessa criatura. O texto permanece disponível caso o usuário queira ativá-lo novamente.
- Importações ficam fechadas inicialmente, com nomes simples: Hunt Analyser e Input Analyser.
- Um controle explícito permite usar ou ignorar o Input Analyser. Importação com dano válido o ativa; colar um Input o ativa também.
- Os textos da interface identificam a consulta de criaturas e as estimativas da Wiki, sem sugerir que importar uma hunt seja obrigatório.

Verificações: análise de uma única criatura sem logs; pesquisa e adição automática na interface; Input anterior inválido ignorado na consulta manual; uma ficha exibida; manutenção da importação de uma hunt com seis criaturas e 57,3% físico; nomes dos painéis e estado inicialmente fechado. Entrega na Beta oficial, sem alteração da estável.
