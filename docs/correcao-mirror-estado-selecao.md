# Correção do estado e da seleção Mirror

## Problemas corrigidos

O Python envia atualizações chamando mirrorEstado(dados), enquanto a interface só havia registrado um listener de evento. A função global ausente causava ReferenceError, impedia a lista de refletir recortes já criados e deixava os controles mostrando uma seleção que havia terminado. Foi adicionada a ponte entre callback e evento, preservando a proteção contra respostas de outro personagem.

O seletor também recriava um bitmap RGBA do tamanho da área cliente a cada tick. Agora quatro janelas de borda de um pixel e uma pequena dica em cache substituem esse bitmap. Ao mover um quadrado, só as posições das janelas mudam; o conteúdo da lupa continua composto por DWM. A geometria já conhecida é reutilizada pelo hook para evitar consultas repetidas em cada evento de mouse.

A ação Posicionar destrava explicitamente um recorte para arrastar no Tibia. Depois, Travar posição restabelece a passagem do mouse. A identificação automática Mirror 1/2 permanece na lista, sem título sobreposto ao jogo; novos recortes começam com título desligado. Títulos personalizados continuam opcionais após renomear o recorte.

## Validação

- A regressão reproduziu ReferenceError antes da correção e passou depois.
- Novo teste Python executa o script gerado por API._emit no ambiente JavaScript da interface; também roda no unittest usado pelo pipeline.
- Confirmação manual por Enter/keyup encerra o estado nativo, remove os hooks e entrega a região selecionada.
- Dois recortes consecutivos são salvos com IDs diferentes e aparecem nos estados emitidos.
- A interface recebe o recorte confirmado, sai da seleção e permite Posicionar/Travar posição.
- Em uma área 4K, o seletor usa menos de 30 mil pixels de bitmaps, em vez de 8,29 milhões; movimento sem redimensionar não faz novo upload de imagem.
- Microbenchmark sintético local de CPU/conversão: mediana de 191,3 ms no bitmap 4K antigo contra 0,035 ms na atualização em cache. Não mede o custo de mover janelas Win32 nem os FPS do Tibia.

Os limites permanecem: sem geração de comandos de jogo, leitura de memória, injeção, alteração do cliente ou contorno de proteção de captura. A correção não altera a composição da imagem do Tibia.
