# Rotina de salvamento dos prints

Em Prints, escolha origem, destino e as opções de copiar/mover e separar por mês. Na seção Rotina de salvamento, ative e salve uma das opções:

- Intervalo: entre 1 e 1440 minutos; primeira execução após o intervalo.
- Vezes por dia: entre 1 e 1440, distribuídas ao longo de 24 horas a partir de um horário de referência. A tela mostra os horários, incluindo madrugada quando aplicável.
- Horários exatos: lista diária no formato HH:MM, separada por vírgulas; horários repetidos são deduplicados.

A rotina organiza screenshots já geradas pelo Tibia. Não captura novas imagens. Usa as pastas e opções gravadas ao salvar; alterações posteriores na tela precisam ser salvas novamente. Funciona com o aplicativo aberto/minimizado, no horário local do computador, e não abre o Explorador automaticamente. Pausar desativa futuras execuções; uma operação já iniciada termina normalmente.

Ao reiniciar o aplicativo, horários passados são ignorados. Após suspensão do computador, executa no máximo uma vez e calcula o próximo horário, sem executar uma sequência de tarefas atrasadas. Operações manuais e automáticas compartilham uma trava; se uma execução manual está em andamento, a rotina tenta novamente em cinco segundos.

Estado e preferências ficam em prints_schedule.json no diretório privado do canal. Gravação atômica; configuração inválida/corrompida fica desativada. Arquivo e cópias temporárias não entram no Git nem nos pacotes. Backup geral inclui a rotina; a restauração aguarda uma execução em curso antes de substituir sua configuração. Não há tarefa do Windows nem execução com o aplicativo fechado.

Testes usam relógio controlado e diretórios temporários para cobrir horários, reinício, suspensão, pause, falhas, concorrência e cópia sem duplicar imagens.
