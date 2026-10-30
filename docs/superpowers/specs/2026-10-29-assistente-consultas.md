# Consultas dos grupos no Assistente Tibiano

O chat do aplicativo aceita as consultas públicas já existentes nos grupos: help, duelo, evolução, preço de TC, pt/party, char/personagem, online e xptop. O engine Bot permanece no servidor; o app compartilha somente o parser de aliases e usa a identidade de instalação protegida por DPAPI. Não é necessário conectar WhatsApp nem liberar o recurso de grupos para fazer consultas.

A rota POST /v1/assistant/command usa a autenticação known existente e seu limite de 60 solicitações/minuto por identidade. Um semáforo limita a quatro consultas simultâneas; o trabalho de rede ocorre no thread pool. Somente text, mundo e personagem públicos são aceitos. Não acessa ponte, inbox, destinos ou GroupConfig; comandos de grupo como set/alerta/bomdia não são executados. O cliente recebe apenas command/text, sem credenciais, configuração privada ou contexto local.

Novos comandos usam Bot com XPProvider.report e track inativo; portanto a leitura do cache não faz HTTP de XP nem acrescenta mundos ao coletor do WhatsApp. A fila de nomes públicos e seus limites continuam os existentes. Char/online conservam o renderer legado e as variáveis dos modelos já salvos. O catálogo de ajustes do Assistente recebe os seis comandos novos e permanece separado dos ajustes do WhatsApp. A prévia administrativa usa o mesmo executor.

No aplicativo, comandos reconhecidos são atendidos antes do NLU/IA. Falha de consulta retorna mensagem controlada e não pede à IA para inventar dados. Frases locais de timers, stamina, shared numérico, Market e os comandos char/online sem prefixo conservam seu caminho anterior. A ajuda visual mostra exemplos e aponta a administração dos grupos para Mensagens. A integração desta mudança é somente no chat de texto. A voz existente permanece intacta.

Testes offline cobrem autenticação sem liberação WhatsApp, whitelist, contexto, modelos, aliases, saturação do semáforo, ausência de envios, roteamento do chat, preservação de frases locais e falhas sem fallback IA. A configuração ZenRows e os coletores não são modificados.
