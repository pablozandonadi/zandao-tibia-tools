# Identidade automática por instalação

## Objetivo e recorte aprovado

Remover Google do fluxo de automação. Cada instalação Windows entra automaticamente em sua própria área e transmite a configuração atual do personagem à gestão local. Preservar geração manual, isolamento de conexões, aceite de riscos, gates administrativos, armazenamento cifrado e fake por padrão. Sem implantar infraestrutura ou usar WhatsApp real nesta etapa.

## Identidade e recuperação

Decisão do coordenador: o desktop gera credencial e recuperação independentes de 256 bits e grava um estado pending com DPAPI CurrentUser **antes** de qualquer registro/rotação. O servidor gera somente owner interno aleatório; persiste apenas hashes SHA-256 de segredos de alta entropia. Nenhum owner fornecido pelo cliente é aceito.

Registro idempotente recebe credencial e recuperação novas; uma repetição com os mesmos hashes recebe o mesmo ack, sem reemitir segredos. Registro público exige limite global de instalações e rate limit global/IP obtido do socket (ignorar X-Forwarded-For). Limites persistentes em SQLite para não resetar por processo/restart; respostas genéricas sem enumeração de contas. Capacidade de instalações explícita e conexões continuam no máximo 50 globais.

Bearer é usado somente por Python para resolver owner. Rotação recebe recuperação antiga e novos segredos já persistidos no Windows; uma transação troca ambos e invalida o acesso antigo mantendo owner, configurações e sessões WhatsApp. Retry após resposta perdida só confirma combinação nova + operação aleatória já gravada; recuperação antiga não autentica novamente. Recuperação exibida apenas por ação explícita local e nunca em logs. Quem possuir o código pode assumir essa instalação; sem código/perfil DPAPI não há recuperação silenciosa nem nova identidade automática.

## Credencial no Windows

Módulo dedicado reutiliza `_proteger`/`_desproteger` de voz_credenciais, sem alterar voz. Arquivo sob LocalAppData/TibiaTudo/automation/{canal}/ com origem HTTPS vinculada, fora de Drive. Canal beta/stable separado. Lock de arquivo entre processos e escrita temporária cifrada + fsync + replace. Falha DPAPI, corrupção, origem divergente ou arquivo existente inválido bloqueiam acesso, sem fallback plaintext/ambiente e sem cadastrar outro owner. Pending inclui segredos novos e dados mínimos para repetir a operação; arquivo não é apagado até ack e finalização durável. Falha de rede ou de escrita final conserva pending e permite retry seguro. Perda de resposta de registro/rotação não cria outro owner.

## Gestão local de confiança

`mensagem_automatica_abrir_portal(config)` abre uma janela pywebview de HTML/CSS/JS **empacotados localmente**, com bridge restrita ao proxy de automação. Nenhuma página remota recebe js_api. Não navegar essa janela para URLs externas. O proxy aceita apenas operações/métodos e caminhos expressamente permitidos (config, conexões, destinos, assinaturas, execuções e recuperação); URL fixa da origem HTTPS administrativa, sem redirect, segmentos IDs validados, tamanho e timeout limitados. Segredo fica em Python, nunca JS/URL/localStorage. Dados de configuração e QR chegam ao JS como dados, com renderização segura. A UI existente é reaproveitada, sem login e sem exigir exportar/importar JSON; configuração atual é entregue no boot por bridge. Export/import opcional pode continuar como arquivo, sem credenciais.

Servidor não serve login remoto nem SDK Google. `/public-config` expõe apenas modo/capacidade; nenhuma autorização depende dele. CORS não substitui bearer. Remover dependência JWT e configuração Google do runtime/runbook em vez de manter dois fluxos.

## Falhas e limites verificáveis

- IP atrás de proxy pode agregar usuários; limite global permanece proteção real. Não confiar headers de proxy sem configuração explícita posterior.
- DPAPI é identidade da instalação/perfil Windows, não comprovação de pessoa. Quem tem acesso ao usuário Windows pode usar a área.
- Código de recuperação exibido sob pedido explícito; cópia é responsabilidade do usuário, sem upload em logs/telemetria.
- Recovery errado/antigo falha; concorrência deixa apenas uma rotação válida. Retry confirmado não altera dados novamente.
- Conteúdo remoto/QR não executa script nem recebe bridge privilegiada.
- Limites não significam suporte ilimitado a jogadores. Sem domínio/origem HTTPS configurada, gestão falha fechada com mensagem clara.

## Validação e entrega

Testes sintéticos: registro idempotente, owner isolado, bearer inválido, rate/capacidade, rotação concorrente/antigo inválido, resposta perdida + retry, DPAPI corrompida e escrita falha, origem/canal/lock, proxy whitelist e redirect, configuração automática no portal local, nenhuma credencial no JS, regressões manuais pertinentes. Assets locais incluídos no packaging e CI offline atualizado. Revisão independente antes de sincronizar G; Git/publicação pelo principal. Nenhuma infraestrutura, conta Google ou WhatsApp real será alterada.

## Decisões finais de revisão

Bearer nunca entra no JavaScript. Exceção estrita para código de recuperação: apenas na janela local confiável, sob ação explícita de mostrar/colar; input password sem autofill, saída via textContent, limpar ao recuperar/sair/pagehide e após 30 segundos. Nada persistido em JS.

Limites aceitos: 500 instalações, 50 conexões globais, 60 pedidos públicos/minuto global e 10/IP. IP fica somente em hash com TTL de até 120 segundos; ambas as cotas são verificadas antes de consumir, sem permitir que um IP bloqueado esgote a cota global. No máximo 100 rotações por instalação limita tombstones a 50 mil. Identidade anônima não prova pessoa nem impede abuso distribuído; capacidade pode ser esgotada e reabertura exige decisão administrativa.

Restore offline revoga todas identidades restauradas e seus códigos, além de conexões/agendas. Não reabilitar automaticamente credenciais de backup; reconciliação administrativa revisada é obrigatória. Credencial/recovery enviados somente em corpo HTTPS, nunca URL/log.
