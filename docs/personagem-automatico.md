# Personagem em uso pelo título do Tibia

15/10/2026. Detecção local do título da janela real do Tibia em primeiro plano. Valida visibilidade, processo e prefixo do título, revalida foco e só encontra nomes já cadastrados, sem diferenciar maiúsculas. Usa o nome canônico salvo. Não interpreta o identificador mostrado no seletor de clientes como parte do título.

Monitor backend com Event.wait(1), início idempotente após a interface estar pronta e parada explícita no finally do aplicativo. Continua ativo com Tibia Tudo minimizado. Logout, título desconhecido, cliente minimizado e outro aplicativo preservam o personagem atual. Não adiciona personagens, não busca nomes na internet e não modifica HWNDs vinculados do Mirror.

Reaproveita a troca manual para atualizar Motor dos timers e MirrorService, com lock comum a seleção/remoção/criação lazy. Reconhecer o mesmo personagem não grava JSON nem reinicia consumidores. Revisão incremental existe apenas no retorno API, sem mudança de schema; callback e respostas antigas não substituem estado mais recente já recebido no navegador. Notificação pendente é repetida se houver falha temporária, sem repetir gravação; novo estado manual invalida retries antigos. Enquanto uma resposta nova está em trânsito, a interface pode continuar mostrando o estado anterior até recebê-la.

Validação: 594 testes completos locais aprovados, mais 53 direcionados após ajuste de invalidação de retry. Chrome headless na página completa confirmou atualização do personagem/lista, descarte de revisão antiga e preservação do campo de cadastro e rascunho da hunt. Revisão independente sem bloqueios. Não foi testado login/troca física no Tibia real nem interleaving de todos os eventos do Windows; detecção nativa testada com mocks. Não usa injeção, leitura/escrita de memória, geração de input, captura ou mudança de proteção do jogo. Não representa aprovação da CipSoft.

Publicação Beta oficial em andamento, canal estável preservado.
