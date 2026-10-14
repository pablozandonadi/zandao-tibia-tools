# Rádio Brasil Hits

A seção Rádio permite ouvir os oito canais da Brasil Hits: Pop, Sertanejo, Pagode, Rock, Dance, Flashback, Latino e Gospel. Escolha o canal e clique em Tocar. Parar encerra a conexão; voltar a tocar retoma a transmissão ao vivo. O programa começa parado e lembra somente canal, qualidade e volume.

O volume da rádio não altera os timers. Depois de abrir a seção, o controle compacto permite parar ou retomar enquanto você usa outras telas. Minimizar mantém a reprodução. O site oficial pode ser aberto pelo botão próprio.

Em uma queda de conexão, o player tenta reconectar quatro vezes com intervalos crescentes. Parar cancela as tentativas. Informações da música são atualizadas a cada 15 segundos durante a reprodução; falha desses dados não interrompe o áudio.

## Validação em 14/10/2026

- WebView2 real: AAC reconhecido, evento playing, readyState 4 e mais de 26 segundos de avanço de mídia.
- Interface real com ponte Python isolada: oito canais, início Parado, reprodução Ao vivo, troca de página e minimização mantendo Ao vivo, parada pelo controle compacto.
- Oito endpoints responderam HTTP 200, audio/aac e entregaram bytes de áudio.
- 494 testes passaram na cópia limpa de develop, incluindo catálogo, URLs, cache, preferências e máquina de estados de reprodução.
- Revisão visual em 1000x720 e 340x640; sem transbordamento horizontal.

Os testes de reprodução foram silenciosos (volume zero). Escuta subjetiva, teste prolongado e instalação/atualização da Beta no computador do usuário permanecem validações adicionais. Uma janela criada inicialmente oculta no experimento não avançou áudio; janela normal e minimização posterior funcionaram.

## Arquitetura

radio_brasilhits.py lê somente catálogo e metadados públicos com timeout, limite de resposta e validação de origens. web/radio.js mantém um único controlador ativo entre páginas e recebe a transmissão diretamente com HTMLAudioElement, sem crossorigin/Web Audio. Não carrega scripts remotos nem incorpora o site com acesso à ponte Python. Recursos incluídos em packaging-resources.json; dados pessoais não são parte do pacote.
