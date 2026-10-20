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

Dois loops locais acompanham os personagens enquanto o aplicativo está aberto,
inclusive minimizado ou em outra tela. UP vem da lista de jogadores online em
`/world`: uma consulta por mundo a cada 60 segundos, compartilhada entre todos os
nomes daquele mundo. A fonte tem cache de 60 segundos; cache e intervalo podem
se somar. Personagens offline mantêm sua última referência e não geram um UP.

Death continua usando `/character` a cada 60 segundos, com cache da fonte de até
cinco minutos. Sem Death, a ficha serve para descobrir/revalidar mundo e vocação
a cada cinco minutos. O level da ficha não substitui o level observado na lista
online. Uma ficha lenta não bloqueia o loop de mundos. Os inícios das chamadas
são espaçados em pelo menos um segundo e limites HTTP 403/429/503 suspendem as
consultas, respeitando Retry-After entre cinco minutos e uma hora.
Os tempos de cache são documentados na [FAQ da TibiaData](https://tibiadata.com/faq/).

A interface lê o estado local a cada segundo e mostra a última verificação e a
fonte de cada personagem; essa leitura não consulta a TibiaData. Os avisos não
são instantâneos. Não há screenshots, leitura do jogo, microfone, envio à OpenAI
nem mudança no Worker.

A primeira resposta válida cria uma referência sem replay de mortes antigas.
Na atualização de uma versão anterior, a primeira leitura do mundo também cria
uma referência silenciosa. Trocar de mundo recria essa referência. Timestamps
da fonte impedem que respostas antigas reduzam o level ou produzam falsos UPs.
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
