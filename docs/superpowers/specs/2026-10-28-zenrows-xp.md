# ZenRows opcional para os rankings XP

O coletor pode tentar primeiro o HTML público GuildStats através do ZenRows, depois a consulta direta e, quando ambas falham, aproveitar o cache TibiaRise existente. A fonte continua GuildStats quando a tabela aceita veio do GuildStats; nada dessa infraestrutura aparece no texto do bom dia.

O cliente usa somente biblioteca padrão, TLS e o endpoint fixo `https://api.zenrows.com/v1/` com `mode=auto`. Destinos aceitos são exclusivamente HTTPS `guildstats.eu`, com caminho e parâmetros permitidos. A integração efetiva desta etapa é somente o ranking `/top-experience`, períodos 0/7/30. Transferências e consultas individuais não foram conectadas ao cliente.

É necessário habilitar explicitamente por ambiente e instalar uma chave em arquivo fora do repositório. Sem habilitação/chave válida, a consulta direta permanece ativa e nenhuma cota é consumida. Nunca salvar chave em testes, Git, pacote, log ou configuração de usuário do aplicativo.

Duas tabelas aditivas controlam tentativas por dia UTC e pausas por recurso/global, em transações imediatas compartilhadas entre processos. Teto padrão 6 tentativas/dia, configurável 0..1000; mesma URL aguarda 6 horas; HTTP401/402/429 pausa todos os pedidos por ao menos uma hora. A cota conta antes da rede, inclusive falhas, e sobrevive a reinícios. Nenhuma recarga/compra ou repetição automática é feita. Contagem de chamadas não é limite financeiro, pois `mode=auto` tem custo variável no fornecedor.

O parser compartilhado exige a tabela GuildStats já conhecida e valores válidos, rejeita páginas de desafio explícitas e não confunde scripts auxiliares ou nomes de personagem com bloqueio. HTML limitado a 6 MB; timeout de conexão/socket 20s, deadline de leitura 25s. Endpoint autenticado sem redirecionamentos. Apenas mensagens controladas saem de falhas, sem URL, chave ou corpo.

O coletor mantém HTTP fora dos comandos. Seu timeout sobe para 180s e lease de mundo para 240s para acomodar até três tentativas adicionais; agendamentos, worker de envios, sessões WhatsApp e dados existentes permanecem intactos. Testes sintéticos cobrem ordem das fontes, desafio, falhas HTTP/timeouts, limites, concorrência, UTC, persistência, segredo e transporte limitado. Ativação e piloto pago ficam a cargo do coordenador após disponibilização segura da chave.
