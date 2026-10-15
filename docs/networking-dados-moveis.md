# Tráfego da sessão e dados móveis — análise em 15/10/2026

Pedido: mostrar enviados e recebidos na sessão por conexão e apenas identificar formas de reduzir ou bloquear o uso do celular. Nenhum bloqueio, alteração de firewall, prioridade, adaptador ou configuração do ExitLag foi aplicado.

## O que a nova contagem mede

O monitor lê os contadores locais InOctets/OutOctets de 64 bits do Windows por adaptador. Conta o tráfego observado de todos os programas do computador nessa conexão, inclusive o monitor e o ExitLag. Não atribui bytes a um processo ou ao Tibia. Não deve ser comparado como valor exato da franquia Claro: o telefone também pode usar dados por conta própria, e a operadora possui outra contabilização. A consulta aos contadores não envia pacotes adicionais; as sondas de conectividade de um segundo continuam tendo seu próprio tráfego.

As linhas de rotas da captura do ExitLag não são somadas pelo monitor. Valores iguais em diversas linhas, sozinhos, não demonstram qual foi o consumo físico total de cada conexão.

Fonte técnica: [GetIfEntry2](https://learn.microsoft.com/en-us/windows/win32/api/netioapi/nf-netioapi-getifentry2) e [MIB_IF_ROW2](https://learn.microsoft.com/en-us/windows/win32/api/netioapi/ns-netioapi-mib_if_row2).

## Possibilidades identificadas, sem implementação

1. **Reduzir atividades do Windows no iPhone USB:** marcar essa conexão Ethernet como uso medido pode reduzir certas atividades de aplicativos e serviços. Isso não é um bloqueio geral e não garante limitar o tráfego do ExitLag. [Microsoft: conexão de uso medido](https://support.microsoft.com/en-us/windows/experience/connectivity-networking/metered-connections-in-windows).
2. **Restringir programas específicos nessa conexão:** o firewall do Windows permite regras por programa e interface. Um bloqueio completo da saída pelo iPhone pode impedir as sondas e o uso dele como reserva; bloquear apenas envio também interfere em conexões que dependem de respostas e confirmações TCP. Não foram criadas nem testadas regras. [Microsoft: New-NetFirewallRule, Program e InterfaceAlias](https://learn.microsoft.com/en-us/powershell/module/netsecurity/new-netfirewallrule?view=windowsserver2025-ps).
3. **Reduzir o tráfego das próprias sondas:** retirar a seleção do iPhone no monitor impede as sondas dessa interface e pausa suas medições. Isso não bloqueia o tráfego de outros aplicativos nem o ExitLag. É um controle já existente; nenhuma seleção foi alterada nesta tarefa.
4. **Rever a participação do celular no ExitLag:** a documentação descreve múltiplos caminhos simultâneos e Multi Internet. Portanto, não é seguro supor que o celular só consome depois de a fibra cair. Não confirmei nas fontes oficiais consultadas uma configuração de reserva que garanta consumo zero enquanto preserva a mesma continuidade. Isso deve ser verificado no aplicativo/suporte antes de qualquer mudança. [ExitLag: funcionamento da tecnologia](https://www.exitlag.com/blog/how-exitlag-works/).

O rádio do próprio aplicativo também reproduz um stream de áudio (web/radio.js), portanto pode ser outra origem de dados quando alcançado pelo celular. Não foi medida sua contribuição, nem a de outros programas, e nada foi pausado ou bloqueado.

## Limites

Foi analisada a possibilidade de bloqueio com documentação oficial; não houve teste de bloqueio ou de failover. Os totais de tráfego são da execução atual, dos períodos monitorados; pausas e lacunas de leitura não são apresentadas como consumo completo. A prioridade é medir primeiro e preservar a proteção da conexão de reserva.
