# Voz

O menu **Voz** reúne os timers criados pelo microfone e pelo formulário. A contagem continua em qualquer página e com o aplicativo minimizado. Cancelar um card cancela somente aquele timer, mesmo quando dois têm a mesma duração. A sessão acaba ao fechar o aplicativo; timers não são persistidos.

Ao abrir o app, o reconhecimento começa automaticamente. No primeiro uso, o serviço baixa aproximadamente 95 MB de modelos gratuitos para `voice_models` na pasta de dados do canal (`%LOCALAPPDATA%/TibiaTudo/beta` ou `stable`). O status mostra o progresso. Depois disso, reconhecimento e fala funcionam localmente. O microfone não é gravado e nenhuma fala é enviada a serviços externos. Pausar o microfone mantém os timers. Em caso de erro, o formulário funciona normalmente; **Tentar novamente** repete a preparação uma vez.

Diga **“Hey Tibia Tudo”**. O assistente responde **“Fala comigo, tibiano”** e espera até oito segundos pelo comando, contados depois da resposta. Também aceita ativação e comando juntos. Exemplos:

- “Novo temporizador de trinta segundos.”
- “Alarme de dois minutos.”
- “Cancelar alarme.”
- “Cancelar temporizador de quarenta segundos.”
- “Cancelar o último alarme.”
- “Qual é meu nível compartilhado?”
- “Até que nível divide experiência?”

O parser aceita timer, temporizador, cronômetro e alarme, com duração inteira de 1 a 180 segundos ou minutos. Com vários timers, cancelar sem duração pergunta qual deles; responda a duração em até oito segundos. Durações equivalentes correspondem (dois minutos e cento e vinte segundos). Havendo duplicados, o cancelamento por voz remove só o mais recente correspondente. Números incertos não criam nem apagam timers.

O reconhecimento Vosk pequeno em português não possui as palavras inglesas exatas “hey”, “timer”, “shared” e “level”. O parser aceita essas formas, mas o reconhecimento real pode exigir “Ei Tíbia Tudo”, “alarme” e “nível compartilhado”. A tela mostra a última transcrição e resposta para diagnosticar. Isso não é uma IA conversacional: são três intenções locais, criação/cancelamento de timer e consulta de shared. Fones reduzem eco do jogo e do próprio assistente.

O shared usa o personagem selecionado e o level salvo pelo Tibia Tudo, lido na mesma pasta de dados da aplicação. As falas ficam em fila; a captação pausa durante a reprodução para reduzir eco. Expirações e contagens não esperam a fila, mas o aviso falado pode esperar uma fala anterior.

O pacote inclui Vosk, PortAudio/sounddevice e Piper/ONNX Runtime na CPU. Não depende do Python nem do ambiente temporário do protótipo na instalação. Modelos não entram no instalador. Downloads usam tamanho e SHA-256 fixados, arquivo temporário e extração com validação de caminho. Preparação e microfone usam thread própria, e a saída de voz usa outra; a UI permanece disponível. Fechar sinaliza encerramento e cancela downloads entre blocos; bibliotecas nativas e leituras de rede em andamento podem levar alguns segundos para retornar.

As dependências estão fixadas com hashes em `requirements-build.lock`. Piper é GPL-3.0; a voz Faber tem licença própria na [ficha do modelo](https://huggingface.co/rhasspy/piper-voices/blob/main/pt/pt_BR/faber/medium/MODEL_CARD). Vosk e modelo português usam Apache 2.0. Verificar microfone, áudio, consumo com jogo e precisão do reconhecimento exige teste real da Beta.
