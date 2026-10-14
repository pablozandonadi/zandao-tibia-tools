# Rede: monitoramento por conexão

Abra **Networking** e clique em **Iniciar monitoramento**. Vivo Fibra e iPhone USB são testados independentemente; não é necessário retirar nenhum cabo. A coleta continua com a janela minimizada e volta a iniciar com o aplicativo se você a deixou habilitada. Para encerrar a coleta, use Pausar monitoramento ou Sair no ícone da bandeja.

- Saudável: cinco rodadas completas abaixo do limiar configurado.
- Instável: latência alta ou somente um dos destinos respondendo.
- Sem acesso confirmado: três rodadas sem resposta dos dois destinos.
- Desconectada: o adaptador deixou de estar operacional.
- Medição indisponível: não foi possível testar essa interface; não significa queda da operadora.

O adaptador pode estar conectado ao cabo e continuar sem acesso externo. Essa é a diferença que o monitor procura mostrar. Um destino externo também pode falhar isoladamente; por isso são usados dois.

A primeira versão mede TCP IPv4 nos endpoints públicos Cloudflare 1.1.1.1:443 e Google 8.8.8.8:443, sem enviar conteúdo de navegação. O gráfico usa sempre Cloudflare; nunca substitui silenciosamente a série por Google. Falhas de sondas representam tentativas sem resposta, não uma medição da perda de pacotes do Tibia. Redes somente IPv6 ficam sem medição nesta versão. VPNs e filtros podem afetar os resultados.

Som e avisos do Windows são configuráveis e disparam nas mudanças de estado, inclusive com a janela minimizada, sujeitos às configurações de notificações do Windows. O histórico visual permite conferir o evento mesmo quando uma notificação não aparece. A marca Minha preferida não altera prioridades do Windows nem o ExitLag. O painel não confirma qual transporte está levando o Tibia e não substitui a proteção Multi Internet do ExitLag.

Adaptadores virtuais e inicialmente desconectados ficam fora da seleção inicial. Use Outros adaptadores para selecioná-los. São permitidas até oito conexões monitoradas simultaneamente. Apelidos e preferências ficam em rede_config.json na pasta de dados do canal; esse arquivo não entra no Git ou no pacote.

A coleta padrão é a cada dois segundos, com alternativas de um ou cinco segundos. As rodadas não se sobrepõem; a cadência pode aumentar quando há muitas interfaces sem resposta. Cada sonda tem timeout de um segundo. O monitor não muda gateways, rotas ou métricas do Windows. Usa IP_UNICAST_IF e bind local; se não conseguir configurar a interface, não tenta a rota padrão.

A memória tem limites: 900 pontos detalhados e 1.440 agregados por minuto por interface, 200 eventos e até 64 adaptadores conhecidos. Os gráficos mostram até cerca de 300 pontos por série. Estatísticas correspondem aos últimos 900 pontos; os gráficos longos usam agregados por minuto. As métricas e eventos são desta sessão e não são gravados em disco. Suspensão e retomada exigem nova confirmação de estabilidade.

## Validação em 14/10/2026

19 testes automatizados cobrem configuração do socket, bloqueio de fallback, timeouts, erro interno, queda, recuperação, falha parcial, latência alta, desconexão, IPv6 sem medição, suspensão, limites e preferências. Na máquina do usuário, com as duas conexões ativas, as sondas vinculadas à Vivo expiraram enquanto o iPhone respondeu, sem alterar ou retirar cabos. Isso confirma a separação observada nesse cenário; não é uma garantia de comportamento sob todo driver ou VPN. Retorno da operadora, ambas as redes sem acesso e notificações do Windows ainda exigem validação de uso real em momento seguro, fora de combate no jogo.
