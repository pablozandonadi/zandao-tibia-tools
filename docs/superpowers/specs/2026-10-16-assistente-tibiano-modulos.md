# Assistente Tibiano — módulos aprovados (16/10/2026)
O usuário aprovou implementar os cinco módulos do PDF de 20 páginas nesta tarefa. Não é somente um plano. Nome e navegação preservam page-voz e hooks existentes.

Decisões: JSON único versionado, substituição atômica e RLock; timers globais por padrão, bosses/stamina por nome de personagem existente; preços privados por mundo e tipo de oferta. Contexto capturado antes da rede. Nenhum áudio/transcrição persistido. Alertas reconciliados uma vez ao reabrir e emitidos apenas com aplicativo aberto. Dados desconhecidos não geram cooldown. Sem gameplay, segredo cliente ou publicação por este programador.

Regras verificadas pelo explorador: shared ceil(2L/3)..floor(3L/2), party 3min>=2max (https://www.tibia.com/support/?entryid=92&subtopic=gethelp); stamina espera 10min e 3:1 até 39h, 6:1 até 42h (https://www.tibia.com/support/?entryid=75&subtopic=gethelp); Bosstiary Bane 25/100/300, Archfoe 5/20/60, Nemesis 1/3/5 (https://www.tibia.com/gameguides/?section=interface&subtopic=manual). Catálogo factual pequeno, cooldown não verificado null.

Confirmação adicional do usuário: histórico Market é adicionado pelo player (formulário/voz), privado por mundo/item/oferta; nenhuma coleta automática. Correções e exclusões guardam before/after auditável. O arquivo possui limite explícito16MiB antes de gravar: não descarta eventos, domínio ou request IDs silenciosamente; ao atingir limite preserva arquivo e solicita backup/arquivamento manual. O app não implementa arquivamento automático. Catálogo inicial só3nomes factuais Archfoe e cooldowns null; importação exige fonte/data/status verificado para cooldown fixo. Boosted do dia é confirmação do player registrada no abate, nunca inferência do modelo.

Validação operacional anterior informada pela coordenação: STT3/3Piper sintético e Nano legadoHTTP200 após32KiB; não é teste de microfone nem validação do novo catálogo em produção.
