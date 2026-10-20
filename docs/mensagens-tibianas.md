# Mensagens tibianas originais

O botão de gerar a Mensagem do dia e o comando `bomdia` incluem uma seção
**💬 Mensagem do dia**, com uma das 60 mensagens originais de humor leve sobre
Tibia. O catálogo está em `mensagens_tibianas.py`; não usa IA nem acesso à rede.

As mensagens são embaralhadas e consumidas sem repetição por 60 gerações. Na
virada de ciclo, a última mensagem não se repete imediatamente. O ciclo fica
somente em memória e recomeça ao abrir novamente o aplicativo. Um lock protege
as gerações concorrentes; nenhum arquivo ou dado pessoal é salvo pelo sorteio.

As referências abaixo serviram apenas para conferir temas e nomes, sem copiar
piadas, descrições ou textos das páginas:

- [Rashid](https://www.tibiawiki.com.br/wiki/Rashid)
- [Pirate Ghost](https://www.tibiawiki.com.br/wiki/Pirate_Ghost)
- [Boots of Haste](https://www.tibiawiki.com.br/wiki/Boots_of_Haste)

As frases não pretendem orientar quests, indicar chances de loot nem prometer
resultados de hunt. Nomes de personagens e guilds dos usuários não fazem parte
do catálogo.
