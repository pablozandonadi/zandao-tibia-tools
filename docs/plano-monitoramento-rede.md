# Plano: painel de conexões e alertas de rede

Data: 14/10/2026. Registro da proposta original. A primeira implementação e seus limites estão documentados em docs/rede.md.

## Problema prioritário

Uma interface pode ter cabo conectado e endereço local, mas estar sem acesso à internet. O usuário precisa testar Vivo Fibra e iPhone USB/Claro simultaneamente, sem desconectar nenhuma delas, e receber aviso quando cada conexão cai ou volta. Suportar N interfaces, com seleção das que devem ser monitoradas. Nunca identificar operadora apenas pelo nome do adaptador: permitir apelidos.

## Proposta de experiência

Nova seção Rede. Faixa superior com resumo: duas conexões saudáveis / apenas uma saudável / nenhuma saudável / verificando. Abaixo, cartões por conexão, com nome, estado, ping atual e médio, perda nas sondas, jitter, último sucesso e tempo saudável observado desde o início do monitoramento ou última recuperação. Mostrar explicitamente Sem internet, Cabo desconectado, Instável, Verificando ou Monitoramento indisponível. Falha interna do monitor nunca significa queda da operadora.

Gráfico temporal compartilhado com cor por conexão, legenda clicável e intervalos 5 min, 1 h e 24 h. Timeouts aparecem como falhas, nunca como ping zero; ausência de coleta aparece como lacuna. Eventos de queda e recuperação ficam marcados. Exibir também pequenos gráficos em cada cartão para comparar conexões com latências muito diferentes. Texto e ícones complementam as cores.

Histórico: horário, conexão, evento e duração. Resumo da sessão: disponibilidade observada, média/p95/máximo de RTT por destino, perda nas sondas, quantidade/duração das quedas e episódios de latência alta. Diferenciar tempo com internet de tempo sem instabilidade; informar a janela de cada métrica. Dados anteriores ao início da coleta são desconhecidos.

Alertas locais visuais e sonoros configuráveis, funcionando com a janela minimizada. Exemplos: Vivo sem acesso confirmado; Claro continua respondendo. Vivo voltou e está saudável há 10 s. Só a Claro está saudável: redundância indisponível. Não repetir notificações a cada amostra. Relembrar opcionalmente após falha prolongada. Preferência Vivo é configuração do usuário, separada da rota observada do Windows.

## O que podemos afirmar

Separar quatro coisas: estado físico do adaptador, acesso externo por interface, rota preferida do Windows para um destino e transporte utilizado pelo ExitLag/Tibia. O tráfego total de um adaptador não identifica o tráfego do jogo. Uma interface pode participar de várias rotas simultaneamente; evitar um selo Principal do Tibia sem evidência.

A captura do usuário mostra endereço local na Vivo, IP público indisponível no ExitLag e aviso de Multi Internet inativo. Isso registra o que a interface do ExitLag informou naquele momento, sem provar sozinho a causa da falha. O ping comum ao Google não testa independentemente as duas interfaces.

## Alternativas consideradas

1. Ping comum ou monitor do navegador: simples, mas pode medir sempre a rota que continua funcionando. Rejeitado como base.
2. Monitor por interface com APIs nativas: recomendado para a primeira versão; atende ao problema sem mexer no roteamento do jogo.
3. Criar substituto de bonding/VPN: projeto distinto, com infraestrutura remota, drivers e riscos de sessão. Fora desta proposta.

## Coleta e confirmação

Motor Python em segundo plano, separado da interface pywebview existente. Enumerar interfaces, endereços e rotas pelas APIs do Windows; usar identidade estável e acompanhar desconexão/reconexão USB e mudanças de IP. Excluir loopback por padrão e identificar VPNs/virtuais separadamente. Não alterar métricas, gateways ou rotas globais.

Etapa técnica obrigatória: provar que cada sonda usa a interface escolhida, inclusive com Vivo fisicamente conectada porém sem acesso e Claro funcionando. Para sockets, avaliar bind do endereço local mais IP_UNICAST_IF/IPV6_UNICAST_IF; ICMP exige implementação nativa compatível e validação própria. Não assumir que bind isolado resolve todos os casos de roteamento ou redirecionamento por VPN. Falha de associação à interface deve resultar em Medição indisponível, sem fallback silencioso para outra rede. Validar também com ExitLag ligado e desligado, sem alterar o processo do jogo.

Sondas leves para pelo menos dois destinos externos independentes; gateway como diagnóstico local separado. Não declarar internet caída por um único destino sem resposta. ICMP bloqueado não prova ausência de internet: confirmar por conexão TCP vinculada à mesma interface, mostrando que RTT TCP e RTT ICMP são métricas diferentes. Não usar serviços sem verificar adequação e limites de sondagem. DNS é diagnóstico independente; resolução compartilhada do Windows não comprova DNS de cada interface. Ping do jogo só quando houver destino e método apropriados; nunca chamar RTT genérico de ping do Tibia.

Proposta inicial de parâmetros, ajustáveis após medição: uma rodada por segundo por interface, timeout próximo de 1 s, no máximo uma rodada pendente por interface, concorrência limitada. Primeiro erro indica suspeita; três rodadas com falhas externas concordantes indicam indisponibilidade provável. Sucesso parcial indica acesso degradado ou falha de destino. Cinco sucessos consecutivos confirmam recuperação; cerca de 10 s saudáveis antes do aviso de estabilidade. Esses números são escolhas de projeto, não medições ou garantias de detecção. Latência alta usa limiar ajustável e comparação com baseline da própria conexão, evitando classificar celular como ruim apenas por ser mais lento que fibra.

## Memória, CPU e dados

Um ping por segundo não exige histórico ilimitado. Buffer circular dos últimos 15 minutos; resumo por minuto para 24 h; retenção local opcional de eventos e agregados por sete dias. Limites explícitos por conexão e globais, expurgo e máximo de interfaces ativamente sondadas configurável. Desenhar no máximo algumas centenas de pontos por série usando agregados que preservem mínimo/máximo e perdas. Coleta continua minimizada, desenho pausa fora da seção. Evitar iniciar PowerShell ou ping.exe a cada segundo; usar APIs e trabalhadores persistentes.

Definir orçamento inicial e medir no Windows real: sem crescimento de memória em teste prolongado, sem sobreposição de sondas e sem travar a UI. Consumo exato depende dos protocolos/destinos e será medido; sondas também gastam dados do celular. Armazenar apenas métricas necessárias, por canal em app_paths, sem registrar IP público, credenciais ou conteúdo do tráfego. Logs e banco pessoais não entram em commits ou pacotes.

## Referências e limites da investigação

ExitLag: documentação oficial apresenta Multi Internet, seleção dinâmica de rotas e redundância. https://www.exitlag.com/products/desktop e https://www.exitlag.com/blog/how-exitlag-works/

Speedify: referência para prioridades, bonding e failover com servidor remoto; documentação distingue isso de balanceamento local sem continuidade garantida das sessões. https://support.speedify.com/article/273-how-speedify-works e https://support.speedify.com/article/996-local-load-balancer

PingPlotter: referência para gráficos de latência, jitter, perdas e correlação temporal. https://www.pingplotter.com/ e https://www.pingplotter.com/manual/displayoptions/

Esses produtos são referências pertinentes; não foi estabelecido ranking de popularidade. Speedify e PingPlotter foram comparados pela documentação oficial, não por engenharia reversa de binários instalados.

REA abriu Y:\ExitLag\ExitLag.exe: PE x86_64, SHA-256 04c9c3cf9e536b6de08267431f8751b94d237aeda2364474667a69e9dc44a06c. Registro local identifica versão 5.23.3. Inspeção portátil de recursos: Evidence ev_f56df20a19e31bbb456ac5aa4ac4af3e3b31d421194169d753ea514a71b81768; isso comprova identidade/estrutura de recursos, não lógica de rede. Busca de strings pelo REA foi bloqueada por provider_unavailable: Ghidra e IDA não configurados; Hopper incompatível com Windows. Algoritmo de failover, API de integração e estado de transporte interno permanecem desconhecidos. Sessão encerrada. Não instalar ferramentas ou atribuir algoritmos ao ExitLag com base em nomes de DLLs. Aprofundamento REA exige configurar um descompilador e obter artefatos oficiais dos concorrentes.

Skill de brainstorming/superpowers não encontrada no catálogo desta sessão nem na busca local em skills/plugins do Claude. Foi feita análise de alternativas sem alegar execução dessa skill.

Microsoft, base para avaliar sondas por interface: https://learn.microsoft.com/en-us/windows/win32/winsock/ipproto-ip-socket-options

## Entregas e critérios de aceitação

1. Prova técnica com sondas isoladas e estados independentes; só avançar se nenhuma conexão mascarar a falha da outra.
2. Motor, testes de transições e armazenamento limitado; simular timeout, destino isolado falhando, todas as redes falhando, retorno intermitente, suspensão e reconexão USB.
3. Tela Rede com cartões, gráficos, filtros, histórico e alertas minimizados; integração via API existente, sem alterar outros módulos pendentes.
4. Validação no Windows: cabo retirado; modem sem acesso mantendo Ethernet conectada; iPhone removido; ambas saudáveis; ambas sem acesso; falha de um alvo; IPv4/IPv6; ExitLag ativo; suspensão/retorno. Desconexões reais somente em momento seguro, fora de uma sessão de jogo.
5. Confirmar queda/recuperação da Vivo sem retirar o iPhone e vice-versa, sem falso saudável por escape da sonda. Medir demora dos alertas e consumo prolongado. Comprovar que pacotes da medição seguem a interface pretendida; contadores gerais não bastam se houver tráfego concorrente.
6. Após implementação: testes relevantes e Beta oficial via cópia temporária, somente arquivos da mudança, commit/push develop, confirmar pipeline e instalador/portátil e fornecer versão/link. Preservar checkout compartilhado. Main/estável aguardam aprovação conforme AGENTS.md.

A proposta original foi seguida pela implementação inicial descrita em docs/rede.md. O monitor não modifica a configuração de rede do sistema.
