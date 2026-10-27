# Fontes de XP resilientes no bot antigo

GuildStats continua como fonte principal. Uma falha HTTP não significa que o personagem está fora do ranking. Guardar respostas válidas com fonte e instante original; dado antigo pode ser mostrado com aviso, mas nunca receber data nova nem virar coleta diária fresca.

Adicionar um histórico separado de XP total TibiaData. Uma coleta só é publicada após validar todas as páginas do mundo. A coleta diária é imutável e vinculada ao dia do Tibia e ao horário de observação; ganhos exigem presença do personagem em dias adjacentes. Janelas de 7/30 dias exigem todos os dias, sem preencher lacunas com zero. Os ganhos calculados são identificados como TibiaData e não substituem o histórico GuildStats existente.

O Commander recebe um provedor persistente; o processamento rápido e sua manutenção só leem cache. A CLI `collect-xp`, em serviço/timer próprios, faz uma coleta limitada por vez, com prazo/TTL/backoff persistente, para não bloquear o worker/WhatsApp nem repetir bloqueios a cada comando. Manter as injeções existentes dos testes. Preservar rotinas, sessões, permissões e entrega sem duplicatas.

Os extras `exp_mundo`, `exp_guild` e `transfer` do bom dia toleram indisponibilidade individual com aviso explícito. XP usa o mesmo provedor; cache GuildStats antigo informa a data sem apresentar números antigos como atuais no bom dia. Diferenças TibiaData mostram os horários originais de início/fim; os metadados distinguem o cálculo local atual das observações upstream. Os 13 blocos principais continuam exigindo fontes válidas, sem relaxar frescor. Os comandos preservam o histórico GuildStats disponível mesmo sem 30 dias completos.

Um delta de duas coletas é rotulado como intervalo, não como XP de ontem. A série complementar usa a data final e mostra início/fim. As variáveis antigas `xp_ontem`, `xp_7d` e `xp_30d` não recebem números TibiaData em modelos personalizados; os números e períodos complementares aparecem fora do modelo. Médias usam o tempo real entre medições.

Corrigir primeiro a mensagem de HTTP 400 da janela local: erro de prévia exibe o motivo de validação do servidor, com tamanho limitado e texto puro. Somente a rota de recuperação sugere conferir o código. Não enfraquecer autenticação nem alterar a identidade.

Não contornar Cloudflare, não enviar mensagens reais e não alterar a VM nesta implementação. O acesso autorizado ao histórico exclusivo GuildStats continua pendente se o fornecedor bloquear as consultas. Não alterar a política de expiração do agendador; o caso `generation_late` está sob investigação separada pelo coordenador.
