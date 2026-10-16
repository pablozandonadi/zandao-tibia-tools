# Voz

O menu **Voz** reúne timers criados pelo microfone e pelo formulário. A contagem continua em qualquer página e com o aplicativo minimizado. Cancelar um card remove somente aquele timer. Timers duram até o aplicativo fechar.

O microfone inicia automaticamente. No primeiro uso, baixa aproximadamente 95 MB de modelos locais para `voice_models`, na pasta de dados Beta ou estável. O status mostra a preparação. **Pausar microfone** preserva os timers; o formulário continua disponível se o reconhecimento falhar.

Diga as três palavras **“Hey Tibia Tudo”**. Um sinal sonoro curto confirma a ativação, sem saudação falada. Você tem oito segundos após o sinal para continuar. Também pode dizer tudo junto: “Hey Tibia Tudo, time trinta minutos” cria um timer de 30 minutos. A esfera liga comandos diretos contínuos, sem repetir a ativação. Clique novamente para voltar à espera por Hey Tibia Tudo. O botão Pausar microfone desliga a captura e o modo direto; ao retomar, o aplicativo volta à espera por ativação. O modo direto não é salvo entre aberturas. Dizer somente “Tibia Tudo”, “Hey Tibia” ou “Hey” não ativa. Após uma ação, use nova ativação.

Exemplos:

- “Coloca um timer de um minuto e meio.” → 90 segundos.
- “Alarme de meio minuto.” → 30 segundos.
- “Cancela o último timer.”
- “Cancela o de dois minutos.”
- “Quanto falta naquele timer?”
- “Qual é minha shared no level 450?”

A voz aceita de 1 segundo a 180 minutos; o formulário permite números inteiros de 1 a 180 por unidade. Vários timers ou durações duplicadas exigem esclarecimento. Responda “o de dois minutos”, “o timer de dois minutos” ou “o último” em até oito segundos após a pergunta terminar. Duração duplicada continua ambígua: escolha o card exato ou diga explicitamente “o último”. Uma nova ordem durante a seleção é ignorada; não cria outro timer. Negações como “não”, “jamais”, “sem criar” e “evite criar” não executam ações; frases com “sem” podem exigir reformulação por segurança.

O shared usa a função do aplicativo e o level informado ou salvo do personagem selecionado. Não busca level ao vivo no jogo. As falas ficam em fila; captura pausa durante Piper para reduzir eco. Avisos de término podem esperar uma fala anterior, mas a contagem não espera.

**Reconhecimento online** é opcional e vem desligado. Em 16/10/2026, após disponibilizar créditos na API, a validação real passou em 3 de 3 casos, incluindo interpretação de comandos (NLU). O Worker está ativo na versão 3a41. O reconhecimento local e os timers continuam disponíveis. Em **Configurações → Acesso de voz (avançado)**, informe o código individual recebido do responsável, marque **Ativar reconhecimento online** e salve. Não é uma chave OpenAI. O acesso fica protegido pelo Windows para seu usuário, separado entre Beta e estável; o campo é limpo após salvar. Para desligar, desmarque e salve. A ativação e a resposta falada continuam locais.

Com online ativo, somente o áudio do comando autorizado por ativação ou pelo modo direto ligado é enviado ao servidor proprietário, que usa OpenAI. Nunca é enviado o segmento anterior à ativação. Quando ativação e comando vêm juntos, o envio depende de timestamps Vosk válidos para cortar o prefixo; caso contrário, permanece no reconhecimento local. O aplicativo não grava áudio. O servidor não persiste áudio nem transcrições; a política de retenção do provedor é separada. Pausa ou troca de configuração invalidam respostas remotas em voo. Falha de rede ou limite usa apenas fallback local, sem repetir a chamada automaticamente.

A operação online tem orçamento global de US$0,20/dia, limite individual de US$0,05/dia e quotas de pedidos. Reservas conservadoras podem bloquear temporariamente novos pedidos mesmo com uso pequeno. Não é serviço ilimitado; detalhes em [gateway](../server/voice-worker/README.md). Transcrição e interpretação reais já foram validadas; a qualidade acústica e a latência durante o uso com jogo e outros aplicativos de voz continuam sujeitas à avaliação no computador do usuário.

O reconhecimento local pequeno pode errar “Hey”, “timer”, “shared” e “level”; aceitar a frase no parser não prova precisão acústica. Prefira headset e acompanhe **Último comando**. A captura usa o limiar existente de energia RMS 300 em blocos de cerca de 100 ms; silêncio abaixo desse limiar não é enviado ao reconhecimento online. A calibração depende do headset e do ruído do ambiente. Uma transcrição local vazia ainda pode seguir online se houver energia de fala em um comando autorizado. A captura descarta overflow e comandos que atingem 15 segundos; não executa áudio truncado. Testes sintéticos não substituem teste real com microfone, jogo, TeamSpeak e Piper.

O pacote usa Vosk, sounddevice/PortAudio e Piper/ONNX Runtime na CPU, com dependências fixadas em `requirements-build.lock`. Os modelos são baixados fora do instalador com tamanho/SHA-256 e validação de caminho. Piper é GPL-3.0; a voz Faber tem [licença própria](https://huggingface.co/rhasspy/piper-voices/blob/main/pt/pt_BR/faber/medium/MODEL_CARD). Vosk e o modelo português usam Apache 2.0. Preparação, captura e saída de voz usam threads; a interface permanece disponível.
