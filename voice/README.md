# Teste descartável de voz — Tibia Tudo

Protótipo separado do aplicativo, gratuito e offline depois da preparação. Não altera o app nem seus dados. Não entra na Beta. O microfone só abre quando você executa o teste. Não grava áudio em arquivo; respostas Piper ficam somente em memória (até 32 frases).

Requer Windows, microfone padrão e Python 3.10 a 3.12 de 64 bits. A resposta padrão usa Piper Faber em português brasileiro, na CPU. Se falhar ao carregar, gerar ou reproduzir, usa a voz do Windows. Não clona sua voz. Prefira fones para reduzir ativações acidentais com jogo e Discord.

No PowerShell, a partir da pasta do projeto:

```powershell
# Prepara Vosk (~31 MB) e Piper Faber (~63 MB), sem abrir microfone:
powershell -NoProfile -ExecutionPolicy Bypass -File .\voice\iniciar_teste.ps1 -PrepareOnly
# Testa lógica com dados fictícios, sem microfone nem voz:
powershell -NoProfile -ExecutionPolicy Bypass -File .\voice\iniciar_teste.ps1 -SelfTest
# Mede geração sem microfone nem reprodução de áudio:
powershell -NoProfile -ExecutionPolicy Bypass -File .\voice\iniciar_teste.ps1 -BenchmarkTts
# Inicia escuta usando os dados da versão estável instalada:
powershell -NoProfile -ExecutionPolicy Bypass -File .\voice\iniciar_teste.ps1
# Alternativa com a voz anterior do Windows:
powershell -NoProfile -ExecutionPolicy Bypass -File .\voice\iniciar_teste.ps1 -Tts windows
```

Se Python não estiver no PATH, acrescente `-Python 'caminho\python.exe'`. Ambiente e modelos ficam em `%TEMP%\tibia-tudo-voice-spike`; a limpeza do TEMP pode exigir baixar novamente. A preparação usa internet para pip e modelos; depois, reconhecimento e respostas são locais. `-SelfTest` e `-NoSpeech` não preparam nem carregam Piper; `-PrepareOnly` prepara a voz selecionada.

Comece com **“Ei Tíbia Tudo, colocar um alarme de trinta segundos”**, **“Ei Tíbia Tudo, ligar um temporizador de vinte e nove minutos”** ou **“Ei Tíbia Tudo, qual é meu nível compartilhado?”**. Também pode dizer a ativação e continuar o comando em até oito segundos. Ao ouvir somente a ativação, responde **“Fala comigo, tibiano”** e abre a janela de oito segundos depois de terminar a fala. Todas as respostas faladas se dirigem a você como tibiano. Pode também dizer ativação e comando na mesma frase, sem aguardar a saudação. “Ei”, “oi” e “Tíbia Tudo” são aceitos.

Os verbos ligar/liga/ligue, gerar/gera/gere, colocar/coloca/coloque, criar/cria/crie, iniciar/inicia/inicie e ativar/ativa/ative são aceitos, com temporizador, cronômetro ou alarme; todos criam a mesma contagem regressiva, sem integração com o relógio do Windows. Use de **1 a 180 segundos ou minutos**, por extenso (incluindo cem e cento e oitenta) ou dígitos no modo texto. Fora dessa faixa, o pedido é rejeitado. Pode usar “de”, “por”, “pra”, “para” ou omitir a ligação: “cria um alarme pra trinta segundos”, “coloca um cronômetro de dois minutos” e “alarme trinta segundos”. Também aceita “novo timer de quarenta segundos” e “timer de dois minutos”. “Um” e “por favor” no início/fim são opcionais; “um alarme para daqui a trinta segundos” também funciona.

O modelo Vosk não contém as palavras exatas “hey”, “timer”, “shared” e “level”. “Timer” pode ser reconhecido como “time”, aceito somente na sintaxe de comando com duração; essa aproximação é experimental. Prefira “temporizador”, “alarme”, “cronômetro” e “nível compartilhado” na voz. A gramática usa fragmentos de ativação, comando e duração para permitir essas combinações sem listar milhares de frases completas. Isso ainda precisa de teste com sua voz e ruído do jogo.

Se houver uma pausa em “ligar alarme” ou “ligar cronômetro de”, o teste aguarda a duração por oito segundos, sem resposta falada no meio: continue com “trinta segundos” ou “vinte e nove minutos”. Após ativação, “dois minutos” sozinho também inicia a contagem. Uma nova ativação ou o fim do prazo descarta o prefixo anterior.

O terminal mostra `Ouvi: ...` apenas depois da ativação e enquanto aguarda o comando, sem salvar em arquivo. Em caso de comando desconhecido, responde “Não entendi. Repita o comando, tibiano.” e permite repetir por oito segundos sem nova ativação. Ruído reconhecido somente como `[unk]` não recebe resposta falada; números incertos não são adivinhados.

Para cancelar, diga **“cancelar timer”**, “excluir temporizador”, “apagar alarme” ou “remover cronômetro”. Com um timer ativo, cancela esse timer; com vários, informa a quantidade e as durações e pergunta qual cancelar. Depois da pergunta, você tem oito segundos para responder “dois minutos”, “de dois minutos” ou “cancelar timer de dois minutos”. Essa resposta cancela, sem criar outro timer. Passado o prazo, é necessária nova ativação. Pode indicar diretamente “cancelar timer de quarenta segundos” ou “cancelar o último timer”. Durações equivalentes (dois minutos e cento e vinte segundos) correspondem ao mesmo tempo. Se houver duplicados com a mesma duração, cancela somente o mais recente correspondente e confirma “um timer ... cancelado”. Timers vencidos não entram na escolha; seus avisos continuam sendo entregues. Números incertos nunca cancelam timers.

A consulta também entende no parser “até que level shareio”, “qual é meu share”, “até que level divide experiência” e “qual meu compartilhado”. Na voz com Vosk, prefira “qual é meu nível compartilhado” ou “até que nível divide experiência”; aceitar a frase em texto não garante que esse modelo a transcreva bem.

O **timer existe somente nesta sessão de teste**: não é criado no aplicativo, não persiste e acaba ao fechar o terminal. Mantenha o processo aberto durante a hunt, inclusive minimizado. Ctrl+C encerra a escuta e descarta timers. O retorno falado suspende temporariamente o reconhecimento para reduzir eco. O aviso de término pode esperar uma resposta falada em andamento.

A consulta lê `meus_personagens.json` a cada pedido, usando o personagem atual e o level salvo pelo próprio Tibia Tudo. Se o personagem atual não existir, segue o app e usa o primeiro personagem. Não busca level ao vivo no jogo nem atualiza o arquivo. O shared arredonda para cima em 2/3 e para baixo em 3/2.

A pasta padrão é `%LOCALAPPDATA%\TibiaTudo\stable`. Use `-Channel beta`, `-Channel source` ou `-DataDir 'pasta dos dados'` para escolher outra origem. Uma alteração ainda não salva pelo app não estará disponível.

Para testar texto sem microfone nem fala:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\voice\iniciar_teste.ps1 -Text 'Ei Tíbia Tudo colocar um alarme de 30 segundos' -NoSpeech
```

O Piper carrega uma vez e gera “Fala comigo, tibiano” antes de abrir o microfone, sem reproduzir o aquecimento. A primeira preparação pode demorar mais; as próximas respostas reutilizam o modelo. O terminal separa tempo de geração e duração do áudio; a reprodução síncrona espera o áudio terminar. Frases repetidas usam cache em memória, limitado a 32 frases. `-BenchmarkTts` mede três frases e repete uma para medir cache, sem consultar dados pessoais, abrir microfone ou reproduzir áudio. No Python direto há `--tts piper/windows`, `--piper-model caminho` e `--benchmark-tts`.

Reconhecimento: [Vosk](https://alphacephei.com/vosk/), modelo `vosk-model-small-pt-0.3` (Apache 2.0), dependências `vosk==0.3.45` e `sounddevice==0.5.5`. Resposta: [Piper](https://github.com/OHF-Voice/piper1-gpl) (`piper-tts==1.3.0`, GPL-3.0) e [voz Faber](https://huggingface.co/rhasspy/piper-voices/tree/main/pt/pt_BR/faber/medium), com licença específica no MODEL_CARD da origem. Este teste não redistribui o modelo.

A precisão da ativação e dos sinônimos, interferência do jogo/Discord, saída de áudio e consumo durante a hunt precisam de avaliação real. Não há cancelamento de ruído. Medições sem reprodução não comprovam a experiência com microfone.
