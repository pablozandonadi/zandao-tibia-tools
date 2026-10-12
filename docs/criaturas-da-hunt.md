# Criaturas da hunt

Menu inspirado no fluxo de busca e seleção de https://tibiahelper.com/Helper/Creatures.
A página original apresenta médias por elemento e resistências das criaturas. A leitura de seu script público retornou HTTP 403; não afirmamos reproduzir uma fórmula interna não verificada.

A lista atual vem das páginas do namespace principal que usam Infobox_Criatura na Tibia Wiki BR. Inclui bosses e variantes. Em 12/10/2026 a consulta retornou 3.437 páginas. Lista e fichas são atualizadas após sete dias, ou pelos botões de atualização. Falhas preservam o cache e aparecem como avisos.

A classificação de dano é a do campo hab_<elemento>, não o nome da magia. Conferências ao vivo: Medusa (físico 0–300, terra 250–450, life drain 100–250); Guzzlemaw (life drain 650–800). Fonte: https://www.tibiawiki.com.br/wiki/Medusa e https://www.tibiawiki.com.br/wiki/Guzzlemaw.

Para cada elemento, o índice médio soma os pontos médios dos ataques listados uma vez cada; a contribuição de cada criatura é multiplicada por peso / soma dos pesos. Sem frequência de ataques não é possível afirmar DPS nem distribuição real. Condições contínuas, campos, habilidades livres, sequências de impactos e faixas desconhecidas são sinalizadas; não se inventam valores. Mana Drain não entra na porcentagem de dano de HP.

Os maiores golpes individuais são ordenados independentemente do peso. Uma criatura rara permanece visível entre os golpes perigosos. Isso não representa chance de crítico ou um combo simultâneo. Recomendações de proteções e respawns ficam para a próxima etapa.

Validação: python -m unittest test_planejador test_web_scripts; node --check web/criaturas.js. A fonte e o catálogo foram consultados ao vivo. Executável recompilado em 12/10/2026 e reaberto. Suíte completa: 242 testes passaram. Recursos do menu e módulo de cálculo verificados no pacote.

## Dados pessoais e cópias do aplicativo

Os módulos atuais salvam dados ao lado do executável. Abrir o executável do projeto em G: e abrir a instalação em LocalAppData usa históricos diferentes. Na investigação de 12/10/2026, a instalação mantinha as 21 hunts e três personagens, enquanto o projeto tinha uma hunt e um personagem. Os dados da instalação foram copiados para o projeto com backup prévio, sem alterar a instalação e sem descartar hunts adicionais por id/assinatura. O backup local está ignorado pelo Git. Reiniciar o aplicativo recarrega os arquivos. Centralizar armazenamento em uma pasta única é uma melhoria futura que exige migração explícita.


## Painel visual e importação

A busca, a composição e as fichas usam os 996 GIFs copiados de Y:\TibiaVision\Resources\creatures, empacotados em web/assets/creatures. Os ícones de dano e proteção vêm dos recursos públicos do TibiaHelper (Content/Images/Dam, Prot, Stats e other). O ícone de afogamento é um SVG local. As imagens e a folha de estilo fazem parte do executável, sem depender da pasta Y:.

O usuário pode colar o Hunting Analyser completo. O parser existente de solo_hunt_core lê apenas Killed Monsters, agrega nomes repetidos e aplica as quantidades como pesos, preservando nomes desconhecidos com aviso. A importação substitui a composição manual e prepara a análise; os pesos podem ser ajustados depois. Party Hunt Analyser sem lista de abates não é aceito. Nada é salvo no histórico de hunts por esta tela.

O relatório mostra cartões de resumo, barras por elemento, gráfico circular da composição, ícones de dano, maiores golpes e fichas expansíveis. As resistências são das criaturas (modificadores de dano recebido), não as proteções do jogador. Dados ausentes têm cobertura explícita e não são tratados como resistência neutra.

Validação desta atualização: 246 testes; interface renderizada no Chrome em 1280 e 580 pixels, com importação, GIFs, ícones e ausência de overflow conferidos. Prévia usa dados reais da Wiki para Flimsy, Freakish e Mean Lost Soul e API simulada apenas para a revisão visual.


## Revisão da distribuição e catálogo

A busca foi limitada aos nomes que têm GIF empacotado (967 correspondências no catálogo atual). Importações descartam criaturas sem GIF com aviso e mantêm a contagem das criaturas suportadas. O índice médio continua exibindo as faixas da Wiki, mas o perfil estimado normaliza os ataques de cada criatura antes de ponderar pela composição. Assim, o número de magias listadas de uma criatura não aumenta seu peso no perfil da hunt. Isso continua sem fornecer frequência de ataques ou distância do jogador.

Received Damage é opcional e independente do Hunting Analyser. Quando colado, a distribuição medida prevalece sem mistura com as faixas da Wiki. Máximos individuais permanecem reportados pela Wiki. O cenário da comparação enviada retorna físico 59,1%, life drain 21%, morte 14% e energia 5,9% com o log medido. Sem Received Damage não se força o físico a dominar; o teste de Icecold Book mantém a predominância de gelo no perfil estimado. Dano e modificadores de resistência são apresentados em ordem decrescente da esquerda para a direita.

Somente o novo menu foi ajustado. Módulos damage_core.py, hunt.py e solo_hunt_core.py mantidos sem alterações nesta revisão. Foram validados logs medidos, ausência de GIF, ordenação de cartões e layout largo/estreito.


## Base BR + TibiaWiki EN (1.0.16)

Snapshot factual de 967 criaturas, armazenado em data/creature_knowledge.json e incluído no instalador. update_creature_knowledge.py atualiza o snapshot com consultas de 50 páginas por requisição às APIs públicas, no máximo três consultas simultâneas. A base inclui faixas confirmadas, resistências, dados básicos e URLs/revisões de origem. Textos descritivos e histórias não são copiados.

Cada ficha consulta as duas Wikis. Dados confirmados em inglês têm prioridade em divergências, que ficam visíveis; campos ausentes na inglesa são completados pela brasileira. Ataques equivalentes entre as fontes são associados para não somar o mesmo golpe duas vezes. Campos marcados como incertos permanecem fora das contas. Resumos Max Damage são preservados em uma seção separada e não viram golpes individuais ou mínimos inventados. Cache antigo é revalidado; falhas de uma fonte preservam seus dados anteriores e permitem nova tentativa após uma hora.

Dworc Shadowstalker: a API brasileira não apresenta faixas; a inglesa declara Life Drain 0–625. O resumo inglês indica físico 250, life drain 625 e morte 100. Os máximos de físico e morte não têm faixas de ataques nesta ficha e não entram na média. Ambas as páginas são ligadas no card, e cada ataque indica a origem. Fonte inglesa: https://tibia.fandom.com/wiki/Dworc_Shadowstalker; brasileira: https://www.tibiawiki.com.br/wiki/Dworc_Shadowstalker.

Botão Limpar lista remove toda a composição, os textos colados e o resultado, para preparar outra hunt. Não altera histórico nem configurações.
