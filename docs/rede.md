# Rede: monitoramento por conexão

Abra **Networking** e clique em **Iniciar monitoramento**. Vivo Fibra e iPhone USB são testados independentemente; não é necessário retirar nenhum cabo. A coleta continua com a janela minimizada e volta a iniciar com o aplicativo se você a deixou habilitada. Para encerrar a coleta, use Pausar monitoramento ou Sair no ícone da bandeja.

- Conectado: pelo menos um destino externo respondeu pela própria interface, independentemente do ping.
- Ping acima de 100 ms: registrado automaticamente no histórico e nos totais, sem som ou notificação.
- Desconectado: retirada do cabo/USB ou duas leituras consecutivas sem resposta dos dois destinos.
- Medição indisponível: não foi possível testar essa interface; não significa queda da operadora.

O adaptador pode estar conectado ao cabo e continuar sem acesso externo. Essa é a diferença que o monitor procura mostrar. Um destino externo também pode falhar isoladamente; por isso são usados dois.

A primeira versão mede TCP IPv4 nos endpoints públicos Cloudflare 1.1.1.1:443 e Google 8.8.8.8:443, sem enviar conteúdo de navegação. O gráfico usa sempre Cloudflare; nunca substitui silenciosamente a série por Google. Falhas de sondas representam tentativas sem resposta, não uma medição da perda de pacotes do Tibia. Redes somente IPv6 ficam sem medição nesta versão. VPNs e filtros podem afetar os resultados.

Som e avisos do Windows são configuráveis e indicam exclusivamente Conectado ou Desconectado, inclusive com a janela minimizada, sujeitos às configurações de notificações do Windows. Oscilações de ping e falhas isoladas das sondas ficam no histórico, sem balão ou som. O histórico visual permite conferir o evento mesmo quando uma notificação não aparece. A marca Minha preferida não altera prioridades do Windows nem o ExitLag. O painel não confirma qual transporte está levando o Tibia e não substitui a proteção Multi Internet do ExitLag.

Adaptadores virtuais e inicialmente desconectados ficam fora da seleção inicial. Use Outros adaptadores para selecioná-los. São permitidas até oito conexões monitoradas simultaneamente. Apelidos e preferências ficam em rede_config.json na pasta de dados do canal; esse arquivo não entra no Git ou no pacote.

A coleta é fixa a cada um segundo, sem seletor de intervalo ou limite de ping. Cada sonda tem timeout de 0,8 segundo, com até 16 sondas concorrentes e sem sobreposição de rodadas. O estado físico dos adaptadores é consultado separadamente a cada 250 ms; a retirada do cabo não aguarda as sondas. Resultados iniciados antes de uma troca de estado/IP são descartados. O monitor não muda gateways, rotas ou métricas do Windows. Usa IP_UNICAST_IF e bind local; se não conseguir configurar a interface, não tenta a rota padrão.

A memória tem limites: 900 pontos detalhados e 1.440 agregados por minuto por interface, 200 eventos e até 64 adaptadores conhecidos. Os gráficos mostram até cerca de 300 pontos por série. Estatísticas correspondem aos últimos 900 pontos; os gráficos longos usam agregados por minuto. As métricas e eventos são desta sessão e não são gravados em disco. Suspensão e retomada exigem nova leitura, sem contar o intervalo suspenso como tempo observado.

## Resumo da tarde ou do período inteiro

O painel Resumo do período monitorado acumula desde o início da coleta nesta execução: leituras, média/maior RTT de Cloudflare, episódios/leituras/tempo acima de 100 ms em qualquer destino, timeouts, falhas das sondas, períodos desconectados, tempo conectado e erros de medição. Ele não perde os totais quando as amostras antigas saem do gráfico. Pausas, suspensão e períodos sem coleta não são contados como tempo observado. Esses totais ficam na memória e reiniciam ao fechar o aplicativo.

O histórico lista as mudanças de conexão, episódios de ping acima de 100 ms com pico e número de leituras, e episódios de falhas/timeouts. Leituras consecutivas do mesmo episódio são agrupadas, sem criar uma linha ou notificação por segundo. Os 200 eventos mais recentes são mantidos, enquanto os contadores do resumo continuam acumulando o período inteiro. Falhas de sondas TCP e timeouts são apresentados separadamente de erro de medição; não são contagem exata de pacotes perdidos pelo jogo.

Os cartões e o resumo atualizam mesmo com checkbox ou rádio em foco. A edição de apelidos e os detalhes abertos são preservados.

## Envio e recebimento por conexão

O resumo mostra **Enviado na sessão** e **Recebido na sessão** para cada interface selecionada, a partir dos contadores de 64 bits do Windows (`GetIfEntry2`). A consulta é local, a cada segundo, e não envia dados adicionais pela internet. Os valores são os bytes de todos os programas no adaptador, incluindo as sondas e tráfego IPv4/IPv6 contabilizado pelo Windows: não medem exclusivamente Tibia/ExitLag nem equivalem à franquia cobrada pela operadora. As linhas de rotas do ExitLag não são somadas.

O primeiro contador válido estabelece o início em zero, sem incluir o uso anterior. Pausar ou retirar a seleção conserva o total; retomar estabelece uma nova referência e não inclui os bytes da pausa. Os valores reiniciam ao fechar o aplicativo. Reinício/reutilização do contador, troca do índice e suspensão longa estabelecem nova referência sem gerar valores negativos ou saltos. Uma falha de consulta preserva os totais já medidos, sinaliza leitura indisponível e não altera o estado conectado/desconectado; o intervalo sem medição fica fora do total. Antes da primeira leitura válida, o total aparece como indisponível.

## Validação em 14/10/2026

19 testes automatizados cobrem configuração do socket, bloqueio de fallback, timeouts, erro interno, queda, recuperação, falha parcial, latência alta, desconexão, IPv6 sem medição, suspensão, limites e preferências. Na máquina do usuário, com as duas conexões ativas, as sondas vinculadas à Vivo expiraram enquanto o iPhone respondeu, sem alterar ou retirar cabos. Isso confirma a separação observada nesse cenário; não é uma garantia de comportamento sob todo driver ou VPN. Retorno da operadora, ambas as redes sem acesso e notificações do Windows ainda exigem validação de uso real em momento seguro, fora de combate no jogo.
