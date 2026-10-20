# Assistente: canais e monitoramento

## Janela única

O Assistente usa uma única barra de canais inspirada no Tibia. Local Chat, Server
Log e Tudo IA são permanentes; Tudo IA permanece na última posição, fixo à direita.
UP Level, Death e Help abrem inicialmente e podem ser fechados e reabertos.
**Abrir canal** reabre UP Level, Death e Help. As ferramentas existentes (timers,
shared, previsão de level, Bosstiary, bosses, stamina e Market) continuam nos
botões superiores, fora da caixa de conversa, com seus formulários preservados.
O botão Chat volta para o canal de conversa anteriormente selecionado.

Somente IDs conhecidos das abas abertas e o ID ativo ficam no localStorage
`zt-assistente-canais-v1`. Preferência inválida ou armazenamento indisponível usa
os canais padrão. As setas, Home e End navegam pelos canais; os seletores aceitam
Enter, duplo clique e Escape. A barra rola horizontalmente em telas estreitas.

## Personagens monitorados

**Monitoramento** cadastra até 20 nomes manualmente ou copia um nome de Meus
personagens. A lista é independente e não altera personagens, levels ou perfis
globais. Cada nome pode monitorar UP Level e/ou Death, ou ser removido.

Uma thread local acompanha os personagens enquanto o aplicativo está aberto,
inclusive minimizado ou em outra tela. Uma consulta pública TibiaData por
personagem combina level e mortes, com intervalo mínimo de 60 segundos. A fonte
pode ter cache e atrasos: os avisos não são instantâneos. Não há leitura do jogo,
microfone, envio à OpenAI nem mudança no Worker.

A primeira resposta válida cria uma referência sem replay de mortes antigas.
Depois disso, aumentos de level geram uma linha com level anterior/novo e horário
**da detecção**. Mortes usam o horário fornecido pela fonte. Identidades estáveis
de mortes evitam duplicação, inclusive após reiniciar. Desligar/religar um tipo
recria a referência desse tipo; falhas preservam a última referência. Resultados
em voo são descartados após remoção ou alteração das opções do personagem.

Os históricos contêm até 200 eventos por canal. Abas fechadas continuam recebendo
eventos; indicadores de não lidas valem durante a sessão e são limpos ao selecionar
o canal. Nomes recebem emoji somente quando a vocação veio na mesma consulta.

O arquivo `monitor-personagens.json`, dentro do diretório privado do canal do app,
contém opções, referências e eventos. A escrita usa lock e substituição atômica.
O arquivo e seu temporário estão excluídos do Git e protegidos pelas regras de
empacotamento/migração. Nomes e eventos não são salvos no localStorage. Um arquivo
inválido é preservado e gera aviso; novo cadastro explícito substitui esse arquivo.
