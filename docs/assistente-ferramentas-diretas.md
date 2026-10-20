# Ferramentas diretas do Assistente

Timers, Shared XP, Stamina e Market usam ações nomeadas, sem seletor genérico de operação. Os bosses mantêm suas ações avançadas existentes. A atualização local preserva os formulários em edição.

- **Timers:** um editor, presets de início, ativos com contagem/fim e histórico recolhido. Renomear preserva o vencimento; alterar o tempo restante começa a contar novamente a partir de agora. Cancelar mantém o registro auditável; repetir cria outro ID.
- **Stamina:** única referência hh:mm e horário local declarado. A estimativa exige offline contínuo; online não desconta uma quantidade de consumo inventada. O alarme de 42h usa `stamina.alert`, é deduplicado e aparece também nos Timers. Corrigir/logout/login invalida alarmes anteriores. Cancelamento por ID e personagem, sem afetar outros personagens. A frase “criar alarme quando minha stamina estiver cheia” executa localmente, sem IA. Meta já alcançada não agenda aviso.
- **Shared XP:** consulta hipotética separada da party. Digitar levels não altera o cadastro; a alteração cadastral fica recolhida e exige confirmação. Só o requisito de level é calculado.
- **Market:** preços manuais privados por mundo, cartões com último preço por compra/venda/negociado e até 100 observações por item. Itens marcados e itens que já têm preço aparecem juntos. Novo preço cria observação; corrigir/excluir exige motivo e mantém a auditoria. As imagens usam o resolvedor de GIF/PNG existente, uma consulta por item nesta sessão, com fallback sem imagem. Imagens não registram preços. Conversão gold/reais e sua cotação existente ficam em uma seção recolhida após os itens.

Alertas são processados pelo serviço existente enquanto o aplicativo está aberto, inclusive minimizado e com voz pausada. Ao reabrir, o Store reconcilia vencimentos uma vez; não há notificação com o aplicativo encerrado. Nenhuma alteração em Worker, modelos ou limites de crédito.

Validação: testes de Store/parser/Chat, canais existentes, conversão, notificador sem DOM legado e interações Chrome em 1400 e 320 pixels, com dados fictícios e APIs locais simuladas.
