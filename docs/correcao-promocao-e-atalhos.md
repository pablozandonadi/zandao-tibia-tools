# Promoção e atalhos — 13/10/2026

A promoção da Beta 32 falhou porque a main já continha a promoção da Beta 27 (estável 1.0.22), em histórico paralelo. A proteção permaneceu ativa: a develop foi reconciliada por merge da main em checkout temporário, sem alterar a main nem o checkout compartilhado. O diagnóstico agora explica a divergência. A Beta 32 não deve ser promovida; analisar a nova Beta antes de clicar em publicar.

Entrega: 1.0.22-beta.35.1, commit 389333ab83e3fe7783112ceda33790e626418410. Pipeline 38416021148 concluído com sucesso, 409 testes. Instalador, portátil, hashes, manifesto e inventário de dependências disponíveis na release.

O instalador copia o cubo para tibia-tudo.ico e todos os atalhos usam IconFilename explicitamente. A atualização remove somente os atalhos legados do seu próprio canal. O executável e o instalador também mantêm o cubo embutido. Ícone com nove resoluções de 16 a 256 pixels.

Validação local: instalador oficial baixado, SHA256 f42628b882cafbd82fcf57c51d24f9e1b3efe36e97fb1b204cc2688e481d4262 conferido, atualização Beta 27 → Beta 35 concluída sem reinício. Registro confirma Beta 35 e produção 1.0.22. Conferidos destino existente e ícone explícito nos dois atalhos da área de trabalho. Atalhos legados e de validação removidos com backup local; aplicações e dados pessoais preservados. Instâncias da validação encerradas. A estável pública não foi republicada: os novos ajustes do instalador irão para produção após aprovação da nova Beta.
