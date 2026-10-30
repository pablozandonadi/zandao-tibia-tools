# Mensagem automática — serviço preparado, sem implantação

Esta pasta contém API, agendador e pontes privadas. **Nada foi implantado, pareado ou enviado ao WhatsApp nesta entrega.** Fake é o padrão. O desktop abre gestão local com configuração atual, sem login Google; Mensagem do dia e World Board manual permanecem intactos.

## Comportamento e limites

- Cada instalação Windows registra automaticamente owner interno aleatório; cliente não fornece owner/JID/caminho/snapshot. Credencial e recuperação independentes de256bits são geradas e gravadas com DPAPI CurrentUser antes de request. Servidor guarda só hashes. Limites:500 instalações,1 conexão/5 assinaturas por owner,50 conexões/500 outras entidades globais,60 requests autenticadas/min,JSON32KB e mensagem16mil caracteres.
- Gestão em pywebview de assets locais empacotados com CSP restrita; página remota nunca recebe bridge. Bearer fica só em Python, nunca JS/URL/log/storage. LocalAppData/TibiaTudo/automation/{beta|stable}, DPAPI CurrentUser, origem HTTPS vinculada, lock e escrita atômica. Corrupção/origem diferente bloqueiam sem nova conta. Rede incerta mantém pending/retry idempotente. Sem plaintext/env secret fallback; proxy de ambiente e redirects recusados.
- Configuração atual entra automaticamente na gestão; export/import de arquivo opcional nunca contém autenticação. Recuperação aparece só por clique explícito e fica no JS local até30s; input password sem autofill, limpar após ação/saída. Quem tem código pode assumir a área. Rotação troca os dois segredos atomicamente, mantém owner/config/sessões e invalida par antigo. Retry confirma só novo par+operação. Escrita final falha preserva pending.
- Nove variáveis, treze blocos e oito extras seguem o contrato puro em `mensagem_automatica_core.py`. Formatação automática é independente; não consome a fila da frase manual. Coleta só fontes selecionadas, força consultas e registra fonte/horário/data. Extras reaproveitam bytecode em namespace privado, também em aplicativo frozen, sem ler fontes `.py` ou modificar módulos globais. Falha/velho/incompleto não vira ausência. Valores manuais dinâmicos precisam de `manualDate` igual à data do Tibia; uma configuração manual não ganha validade diária automaticamente.
- Horários IANA no mesmo dia local: envio ≥ geração, inicialmente vazios. Referência Tibia muda às 10h de `Europe/Berlin`. Horário DST inexistente expira; repetido usa primeira ocorrência. Cruzar server save durante atraso/coleta/espera impede envio daquele snapshot. Relógio é atualizado entre fases. Atraso máximo: 30 minutos; revalidar validade dos dados no envio.
- Dedup persistente por dono/assinatura/destino/data e versão da configuração. Geração transitória tem no máximo 3 tentativas, esperas 60s/120s, dentro da janela e referência; erro de configuração/dados inválidos não repete. Timeout após despacho/crash em `sending` vira `uncertain`, sem repetição cega. Resposta de aceitação não prova entrega ou leitura. Falha conhecida antes de iniciar despacho fica `failed/transport_not_started` e não é repetida automaticamente.
- Revogar invalida banco e agenda antes de pedir logout à ponte. Despacho já iniciado pode ter chegado ao destino; fica incerto se revogação correr em paralelo. A ponte serializa envio/revogação por sessão. Não há promessa de recall ou entrega exatamente uma vez.
- SQLite da API cifra conteúdo/configurações/destinos/relatórios com Fernet e vínculo autenticado ao dono/ID. Chave fora de banco/repositório/estado. A ponte escolhida (Go/whatsmeow ou Node/Baileys) usa SQLite em **mount Linux LUKS/dm-crypt real**; o preflight verifica mountinfo + UUID `CRYPT-LUKS`, não uma flag declarativa. Isso é pré-condição de implantação, não criptografia SQLite implementada na biblioteca. Chave LUKS deve ficar fora do volume e do backup. Não há varredura/reconexão no startup: só uma conexão ativa resolvida no backend pode pedir `/resume` antes de enviar.
- Integração **não oficial** whatsmeow, distinta da API oficial Meta. Pode quebrar ou resultar em bloqueio; cada proprietário deve aceitar antes de parear. Não há leitura/armazenamento de caixa de entrada nem chamada `MarkRead`, nenhum handler de mensagens recebidas, download de histórico ou persistência de retry de conteúdo. O protocolo ainda pode receber eventos e emitir acks de entrega; isso não é recibo de leitura. Não confirmar leitura de intimações nem prometer efeitos jurídicos. Ausência de recibos de leitura deve ser validada em ambiente controlado antes de uso real.

## Verificação local, sem credenciais

Use Python 3.12+, Go 1.27.3 e Node com Playwright. Instale dependências somente no ambiente do serviço, não no desktop:

```sh
cd server/message-automation
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest -v test_automation
.venv/bin/python -m automation demo
cd bridge
go test ./...
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -trimpath -o ../message-bridge .
```

`demo` usa somente dados sintéticos/fake. Testes API cobrem registro/ownership/rotação/retry/quotas/restore; desktop testa DPAPI sintético; gestão usa bridge nativa simulada sem Google/API via fetch. CI cobre core/demo/gestão/Go/Baileys sem contas ou WhatsApp reais.

## Implantação após aprovações — comandos preparados, não executados

1. Confirmar conta/região Oracle, quota e disponibilidade Always Free no Console, custos de cada recurso e autorização para provisionar. [Documentação Oracle](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm): A1 até 1.500 OCPU-h e 9.000 GB-h/mês, equivalente a 2 OCPUs/12 GB para tenancy Always Free; conferir novamente no momento de criar. Capacidade pode faltar e instâncias ociosas podem ser recuperadas; não há garantia de serviço contínuo. Não criar recurso pago ou alterar plano implicitamente. Runtime não precisa de credenciais OCI.

2. Após aprovação, preparar VM Linux mantida e checkout revisado em `/opt/zandaotools`, somente leitura para usuários de serviço. Instalar Python/venv/Go compatíveis com a imagem confirmada, construir acima e verificar hashes. Não copiar perfil, cookies, sessões ou dados do PC. Reservar volume cifrado LUKS para `/var/lib/zt-whatsapp`; seleção/formatação do dispositivo depende de identificação do volume real e procedimento de infraestrutura aprovado, sem comandos destrutivos genéricos neste roteiro. Montar antes do modo real e guardar chave fora do volume.

3. Criar usuários/segredos fora do checkout. Comandos administrativos abaixo são para o operador revisar na VM preparada:

```sh
sudo useradd --system --home /nonexistent --shell /usr/sbin/nologin zt-automation
sudo useradd --system --home /nonexistent --shell /usr/sbin/nologin zt-whatsapp
sudo install -d -m 0750 -o root -g zt-automation /etc/zt-automation
sudo install -d -m 0750 -o root -g zt-whatsapp /etc/zt-whatsapp
sudo install -d -m 0700 -o zt-automation -g zt-automation /var/lib/zt-automation
# /var/lib/zt-whatsapp deve ser o mount cifrado aprovado, pertencente a zt-whatsapp.
sudo sh -c 'umask 077; /opt/zandaotools/server/message-automation/.venv/bin/python -c "from cryptography.fernet import Fernet; open(\"/etc/zt-automation/data.key\",\"wb\").write(Fernet.generate_key())"'
sudo chown root:zt-automation /etc/zt-automation/data.key
sudo chmod 0640 /etc/zt-automation/data.key
sudo sh -c 'umask 077; openssl rand -hex 32 > /etc/zt-automation/bridge.token'
sudo install -m 0640 -o root -g zt-whatsapp /etc/zt-automation/bridge.token /etc/zt-whatsapp/bridge.token
sudo chown root:zt-automation /etc/zt-automation/bridge.token
sudo chmod 0640 /etc/zt-automation/bridge.token
sudo install -m 0640 -o root -g zt-automation deploy/service.env.example /etc/zt-automation/service.env
sudo install -m 0640 -o root -g zt-whatsapp deploy/bridge.env.example /etc/zt-whatsapp/bridge.env
```

Se os usuários ou segredos já existirem, preservar e reconciliar; **não gerar novamente chaves de um serviço com dados existentes**. Não imprimir chaves/tokens nem incluí-los em terminal compartilhado, logs, screenshots ou Git.

4. Configurar origem HTTPS administrativa. Desktop usa `AUTOMATION_PORTAL_URL=https://SEU-DOMINIO` (sem segredo); `/portal` legado é normalizado para origem. Não precisa Client ID/conta Google. Gestão é local; `/portal` remoto só instrui abrir aplicativo. `AUTOMATION_ORIGINS` fica vazio salvo origem explícita confiável. Não habilitar proxy headers: IP vem do socket e ignora X-Forwarded-For.

5. Configurar proxy HTTPS para `127.0.0.1:8787`, TLS válido, limite de corpo **32k**, limites de conexão/requisição e origem exata. Não registrar Authorization, cookies, corpo, query ou QR no proxy. Permitir público somente HTTPS; SSH restrito ao IP administrativo; 8787/8788 e bancos nunca públicos. Saída precisa atender fontes públicas, quando autorizado, WhatsApp. Validar destinos reais antes de restringir egress; não inventar allowlist incompatível. Sincronizar relógio da VM.

6. Instalar unidades com API/worker sem root, código protegido e diretórios de estado específicos. Units não concedem OCI IAM. Na pasta do serviço:

```sh
sudo install -m 0644 deploy/zt-automation-api.service deploy/zt-automation-worker.service deploy/zt-automation-worker.timer deploy/zt-whatsapp-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemd-analyze verify /etc/systemd/system/zt-automation-api.service /etc/systemd/system/zt-automation-worker.service /etc/systemd/system/zt-whatsapp-bridge.service
# Somente depois de revisar env, mounts, domínio e login:
sudo systemctl enable --now zt-automation-api.service zt-automation-worker.timer
```

O modo inicial continua fake e não precisa iniciar ponte. Executar a demo e validar API/gestão com identidade sintética; revisar prévia e logs antes de solicitar uso real. `deploy/logging.json` permite apenas eventos operacionais controlados; nunca usar debug/protocol dumps. Definir retenção de logs de 14 dias no destino operacional e backups cifrados diários de 7 dias. Não alterar retenção global de outros serviços por efeito colateral.

7. Somente após aprovação separada de pareamento/teste, verificar mount cifrado e mudar **ambos** os arquivos administrativos: Python `AUTOMATION_TRANSPORT=bridge`, `AUTOMATION_ENABLE_REAL=I_ACCEPT_UNOFFICIAL_WHATSAPP`; ponte `BRIDGE_MODE=real`, `BRIDGE_ENABLE_REAL=I_ACCEPT_UNOFFICIAL_WHATSAPP`. Reiniciar API/worker e iniciar ponte. Sem isso nenhum usuário habilita modo real só pelo navegador. Cada proprietário aceita os riscos, pede QR temporário, atualiza status/grupos e escolhe grupo opaco. QR pode demorar a aparecer; usar Atualizar conexão. Logout exige novo pareamento; revogação não reutiliza a sessão.

8. Confirmar grupo de teste/texto/destinatários antes de **qualquer** mensagem real. Esta versão não executou esse teste. A ativação no portal agenda mensagens reais se o transporte administrativo for real: só clicar depois da autorização específica do proprietário. Para teste controlado, usar um grupo de teste autorizado e horários próximos, conferir resultado e pausar. Essa autorização não ativa outras contas. Validar não emissão de recibo de leitura antes do uso habitual.

## Backup, restore e reversão

Executar backup com o mesmo usuário e arquivo de ambiente administrativo carregado; argumentos nunca contêm segredos. O comando faz snapshot SQLite consistente em memória e grava **somente ciphertext** em arquivo privado; rejeita o banco ativo e aliases como destino:

```sh
# Ambiente carregado pelo operador, ou unidade oneshot equivalente com EnvironmentFile.
.venv/bin/python -m automation backup --file /CAMINHO-PRIVADO/automation-backup.fernet
```

Guardar cópia cifrada fora da VM e chave de dados separadamente. Sessões da ponte não entram nesse arquivo. Se precisarem de backup, capturar volume LUKS com ponte parada, com proteção própria e chave separada; não exportar SQLite de sessão em texto claro. Credenciais cifradas continuam sensíveis.

Restore é sempre **offline**: parar API, timer/worker e ponte, bloquear a rede da ponte, manter `AUTOMATION_TRANSPORT=fake`. Não restaurar arquivos sobre serviço em execução. Guardar cópia cifrada do estado atual antes de substituir. Com ambiente administrativo carregado:

```sh
sudo systemctl stop zt-automation-worker.timer zt-automation-worker.service zt-automation-api.service zt-whatsapp-bridge.service
.venv/bin/python -m automation restore-offline --services-stopped --file /CAMINHO-PRIVADO/automation-backup.fernet
```

O restore invalida **todas** as conexões e pausa assinaturas, inclusive sessões presentes no backup. Não reconectar sessões antigas ao restaurar volume: preservar tombstones `.revoked`, manter arquivos antigos isolados sem rede, e exigir novos IDs/pareamento para todos os usuários. A ponte não reconecta diretórios no startup. Isso impede que o backup ressuscite revogação; sacrifica reconexão automática após recuperação de desastre. Verificar offline que conexões estão `revoked`, assinaturas `inactive` e nada despacha, antes de reabrir rede. Testar restauração regularmente sem WhatsApp e sem credenciais reais.

Reversão operacional: parar timer, pausar assinaturas, configurar transporte fake, revogar conexões se necessário e restaurar código revisado anterior com dados/backup compatíveis. Não reexecutar `uncertain`: investigar a tentativa e obter decisão do dono, evitando duplicatas. Alterações de configuração cancelam trabalhos antigos; não reenviam a mesma chave/data silenciosamente.

## Pendências para uso real

Compatibilidade de desenvolvimento: um checkout compartilhado antigo pode conter `comandos_tibia.py` anterior ao contrato `EXTRAS`/`extra`. A sincronização preserva esse módulo e seu fluxo manual. Nesse caso, geração básica e demo continuam disponíveis; selecionar consultas extras retorna um erro controlado pedindo atualização dos módulos, sem inventar resultados ou repetir como falha transitória. A Beta/develop coesa contém o contrato completo e mantém os sete extras funcionais. O módulo público `mensagens_tibianas.py`, quando ausente, precisa acompanhar os novos helpers; não copiar dados pessoais para preencher dependências.

Conta/região/quota/volume Oracle e autorização de infraestrutura; domínio/TLS; confirmar mundo/horários/fuso; aprovação individual de riscos/pareamento; grupo e texto do teste real; verificação controlada de ausência de recibos de leitura e ativação final. VM, firewall, TLS, systemd e WhatsApp não foram alterados por esta entrega. A documentação não constitui confirmação de leitura de mensagens ou intimações.

Alternativa privada Node/Baileys e limites de migração: [bridge-baileys/README.md](bridge-baileys/README.md). Escolher somente uma ponte; nenhuma sessão legada é adotada automaticamente.

## Identidade anônima e recuperação

Registro/recovery públicos:60/min global e10/IP persistentes em SQLite, somente hashIP,TTL até120s. Validar ambas cotas antes de incrementar. Não prova pessoa nem impede bots distribuídos: podem esgotar500 cadastros; reabrir capacidade exige decisão administrativa revisada. Máximo100 rotações/owner limita tombstones a50mil. Não aumentar quotas automaticamente.

Guardar código por ação explícita; sem DPAPI/código não há recuperação silenciosa. Rejeição definitiva preserva acesso anterior válido; resultado de rede incerto conserva pending e exige retomar antes de outra recuperação. Nunca apagar arquivo protegido para contornar erro. Código errado em instalação nova pode ser corrigido explicitamente sem gerar outro owner.

Restore offline revoga TODAS identidades/códigos restaurados, além de conexões/agendas. Backup não ressuscita acesso revogado. Reconciliação administrativa posterior obrigatória; sem claim automático ou adoção da sessão legada. Parar todos serviços e bloquear rede da ponte até reconciliar.

## Alertas da guild (mortes e level up)

Recurso só de envio: o servidor consulta a lista pública da guild e a ficha pública dos membros (TibiaData) a cada 20 segundos (o `tick` de 1 minuto do worker faz 3 varreduras, em 0, 20 e 40 s). Level up vem da lista de online do mundo (atual, a mesma fonte do UP Level do app) e não da lista da guild, que a TibiaData entrega com level atrasado; a guild só diz quem é membro e é renovada a cada 15 min. As fichas (mortes) são conferidas na mesma cadência, em rodízio entre os membros online e manda **uma mensagem por evento** ao grupo escolhido. Nada do que os membros escrevem no grupo é lido; o bom dia segue pelas rotinas diárias.

- **Objeto `watch`** (até 3 por instalação): `guild`, `milestone` (level up a cada N níveis: 1 = todo level, padrão; 50 = só em 100, 150, 200…), `deaths`, `ups`, `hourlyCap` (teto de avisos por hora; 0 = sem limite, padrão), `perMinute` (ritmo de envio de 1 a 120 por minuto, padrão 3), `connection`, `destination`. API: `GET/POST /v1/watches`, `PUT/DELETE /v1/watches/{id}`; mesmas regras de dono, conexão ativa e grupo autorizado das rotinas.
- **Sem retroativo:** a primeira varredura só memoriza os levels; mortes anteriores à criação do alerta são ignoradas. Cada evento tem chave única (`up:nome:marco`, `death:nome:horário`), então nunca repete, mesmo se o personagem perder e recuperar o level.
- **Proteções do número:** no máximo 3 mensagens por minuto e o teto por hora configurado; aviso que não coube e passou de 3 h expira em vez de chegar atrasado. Envio registrado antes do despacho: falha conhecida vira `failed`, resposta duvidosa vira `uncertain` e nunca é repetida. Revogar a conexão cancela a fila.
- **Conteúdo:** nomes vindos do jogo perdem `*`, `_`, `~`, crase e quebras de linha antes de entrar na mensagem. Texto do evento é cifrado no banco como os demais conteúdos.
- **Falha fechada:** guild vazia ou fonte fora do ar não gera evento nem apaga a memória de levels.
- **Implantação:** atualizar o checkout da VM (`zt-deploy.sh`) cria as tabelas `watch_*` sozinho; nenhuma unidade systemd nova. Testes: `python -m unittest test_watch` em `server/message-automation`.

## Comandos no grupo (!help, !duelo, !evolucao, !precocoin)

O bot responde a comandos escritos no grupo. Ele **lê apenas linhas que começam com `!`** (até 200 caracteres); todo o resto é descartado na própria ponte, sem gravar nem registrar. As linhas ficam só em memória (máx. 100, validade de 3 min) até o servidor lê-las a cada 20 s (`POST /sessions/<id>/inbox`, loopback e token da ponte).

- **Objeto `botgroup`** (até 3 por instalação, um ativo por grupo): `world` (mundo padrão), `cooldown` (5 a 600 s por membro, padrão 30), `connection`, `destination`. API: `GET/POST /v1/botgroups`, `PUT/DELETE /v1/botgroups/{id}`; mesmas regras de dono, conexão ativa e grupo autorizado.
- **Comandos:** `!help`; `!pt personagem [voc]` (party finder: jogadores online do mundo dentro da faixa de shared XP, de 2/3 a 3/2 do level, agrupados por vocação); `!char nome` (ficha completa de qualquer mundo, no conteúdo do `char` do app); `!online mundo|guild` (jogadores online agora); `!xptop personagem` (XP dia a dia gravado pelo servidor, com resumo do GuildStats); `!precocoin [mundo]` (TibiaTrade, a mesma cotação do Market do app, pacote padrão de 250 TC por R$ 49 a R$ 52); `!duelo a x b` (level, XP em 30 dias, por dia, 7 dias e ontem do ranking do GuildStats, mais quem passa quem no ritmo atual); `!evolucao nome` (XP de ontem, 7 e 30 dias, projeção do próximo level e curva diária). Ao receber um comando conhecido o bot mostra "digitando…" no grupo (rota `POST /sessions/<id>/typing` da ponte) até a resposta sair; a fila de comandos é lida a cada 2 s. Comando desconhecido não gera resposta (outros bots no grupo não são atrapalhados).
- **Limites e privacidade:** 1 comando a cada N s por membro (dentro do intervalo, silêncio), no máximo 5 comandos por varredura, grupo não autorizado ignorado. O servidor guarda só o id da mensagem (para não responder duas vezes) e o horário do último uso por membro (identificador opaco, HMAC); o texto recebido nunca é gravado. Nomes vindos do jogo perdem `*`, `_`, `~`, crase e quebras de linha antes de entrar na resposta.
- **Histórico de XP:** a TibiaData não tem histórico e o GuildStats protege a aba diária. O servidor grava, uma vez por dia depois do meio-dia de Berlim, o ranking de "ontem" (top 500) de cada mundo usado (tabela `rank_history`, 60 dias); a curva diária do `!evolucao` aparece conforme os dias acumulam. Personagem fora do top 500 do mundo não tem dados de XP.
- **Implantação:** além do código do servidor, é preciso trocar o binário da ponte (`message-bridge`) e reiniciar `zt-whatsapp-bridge`; a sessão do WhatsApp fica no volume cifrado e volta a conectar na próxima chamada. Testes: `python -m unittest test_commands` (servidor) e `go test ./...` (ponte).


## Recurso fechado e código do dono

O serviço só atende contas **liberadas** (tabela `entitlements`); as demais recebem `403` ("Este recurso ainda não está disponível para a sua conta"). Quem já tinha dados quando a regra entrou continua liberado (migração única); instalações novas não entram sozinhas. Vigia, comandos e rotinas diárias também ignoram contas sem liberação.

- **Liberar por código:** `python -m automation claim-code --note dono` gera um código de 43 caracteres, mostrado uma única vez (o servidor guarda só o hash). No app, em Configurações › "Tenho um código de acesso", `POST /v1/claim` libera a conta de quem digita (máx. 5 tentativas a cada 10 min por conta). `--uses 1` cria um código de uso único (modelo para o plano pago).
- **Liberar/retirar pela linha de comando:** `python -m automation owners` (lista contas e se estão liberadas), `grant --owner ID --note texto` e `ungrant --owner ID`.
- **Trocar de computador:** instale o app, abra Configurações › "Tenho um código de acesso" e cole o mesmo código do dono. Ele libera a nova conta no servidor e o menu Mensagens e o Admin no app. O Admin ainda pede a senha do Admin (a do Worker de IA). As rotinas, alertas e comandos criados no PC antigo ficam na conta antiga: use "Recuperar acesso em outro computador" (código de recuperação) para trazê-los.
- **Códigos para clientes que pagam:** a conta que ativou o código `dono` vira *administradora*. No app, menu Admin › "Acesso ao menu Mensagens (clientes)", ela gera um código por cliente (nome + quantos PCs podem usar, 1 a 1000), vê quantos usos restam, revoga códigos ainda não usados e remove o acesso de uma conta de cliente. O código aparece uma única vez; o servidor guarda só o hash. Rotas `GET/POST /v1/admin/claims`, `DELETE /v1/admin/claims/{id}`, `GET /v1/admin/accounts`, `DELETE /v1/admin/accounts/{id}` respondem `403` para quem não é administrador. Código de cliente libera só o menu Mensagens (nunca o Admin). Quem já era dono antes desta versão precisa colar o código `dono` de novo para virar administrador. O pagamento (Pix) ainda não existe: por enquanto o admin gera o código à mão.
- **Comandos dos bots (Admin › "Comandos dos bots"):** o administrador liga/desliga cada comando e define o texto da resposta, para o bot do WhatsApp (`whatsapp`: !help, !duelo, !evolucao, !precocoin, !pt, !char, !online, !xptop) e para o assistente do app (`assistente`: bom dia, kill, boss, online, char, death, guild, exp). Sem ajuste = comportamento padrão. Comando desligado fica em silêncio. O texto é um modelo com variáveis entre chaves: no WhatsApp cada comando tem as suas (`{mundo}`, `{preco}`, `{tabela}`…), e o modelo padrão reproduz a resposta de hoje; no assistente (que também alimenta a Mensagem do dia) valem `{titulo}`, `{corpo}`, `{argumento}`, `{mundo}`, `{personagem}`. `{resposta}` é a resposta padrão inteira. Linha só de variáveis vazias some; texto sem nenhuma variável é uma resposta fixa (sem consultar as fontes); avisos de uso e de erro não passam pelo modelo. `POST /v1/admin/botcmds/preview` roda o comando de verdade com o modelo ainda não salvo (a prévia do Admin). Comando novo precisa entrar em `BOT_COMMANDS` e no catálogo (`MODELS` em `botcmds.py` ou `MODELOS` em `comandos_tibia.py`); um teste cobre isso. Rotas `GET /v1/admin/botcmds`, `PUT|DELETE /v1/admin/botcmds/{bot}/{comando}` (só administrador). O app de todos os usuários lê só os ajustes do assistente em `GET /public/botcmds` (sem login, cache de 5 min, em segundo plano; sem servidor, vale o padrão). Tabela `bot_settings`.
- **Configuração pelo grupo (`!set` e `!alerta`):** qualquer **administrador do grupo** pode ajustar o bot sem abrir o app. A ponte (`bridge/main.go`) consulta o WhatsApp (`GetGroupInfo`) só para as linhas `!set`/`!alerta` e marca `admin:true` quando o autor é admin (confere telefone e LID); sem confirmação, vale `false`. Só grupos já cadastrados no app e só dentro dos limites do dono (3 alertas, 3 grupos de comandos). Comandos: `!set` (resumo), `!set world <mundo>`, `!set cooldown 30|30s|2m|1h` (3 s a 24 h; admins configuram sem esperar), `!set comandos on/off` (pausa o bot no grupo, `!set` continua valendo), `!set cmd <comando> on/off` (desliga um comando só ali), `!alerta guild <nome>`, `!alerta level <n>`, `!alerta mortes|ups on/off`, `!alerta limite hora|minuto <n>`, `!alerta on/off/remover`. Não-admin recebe uma recusa (sujeita ao intervalo por pessoa). No app, o dono vê a marca "criado pelo grupo"/"ajustado pelo grupo" e pode bloquear tudo com a chave "Bloquear configuração pelo grupo" (`groupConfig` do grupo de comandos). Campos novos: `botgroup.{groupConfig,paused,disabled,changedByGroup}` e `watch.{source,createdAt,changedByGroup}`. Código em `automation/groupcfg.py`. O app mostra tudo isso no painel da página Mensagens (uma linha por grupo); para isso `GET /v1/botgroups` devolve `lastUse` (último comando usado, epoch) e `GET /v1/watches` devolve `lastSent` (último aviso enviado), nunca quem usou nem o texto. **Bom dia pelo grupo:** `!bomdia` (estado), `!bomdia on|off`, `!bomdia horario <hh:mm>` (horário de Brasília; a mensagem é montada 10 min antes), `!bomdia remover`. Cria uma rotina (`subscription`) deste grupo com **os 13 itens sempre ligados** (data, saudação, mensagem do dia, mundo, eventos do Tibia, Yasir, Rashid, criatura boostada, boss boostado, Dream Court, mortes do Dream Court, outras world changes e próximo SS) e a assinatura fixa "TibiaTudo IA, acesso o site https://tibia-tudo.web.app / by Zandão" (único campo manual que aceita quebra de linha). Padrão 06:00; segue o mundo do `!set world`; se já existir rotina ativa criada no app para o mesmo grupo, recusa. Pausar ou editar pelo app mantém a marca `source:'group'`.
- **No app:** o menu Mensagens e o Admin só aparecem com o arquivo local `recursos-dono.json` (gravado ao aceitar o código). Esconder o menu é só comodidade: a barreira real é o `403` do servidor.

## Fontes de XP e falhas de consulta (27/10/2026)

GuildStats permanece principal. `xp_rank_cache` guarda o resultado válido cifrado e seu instante original; HTTP 403 é bloqueio, não personagem fora do ranking. Comandos mostram dados antigos somente com fonte/data explícitas e sem projeção. A tabela antiga `rank_history` é preservada e continua visível mesmo quando faltam 30 dias de dados.

TibiaData é um complemento separado (`xp_totals`): até 20 páginas/1.000 personagens por mundo, somente uma coleta completa validada vira snapshot. Mundo/categoria/vocação/paginação/posições/nomes/XP e timestamps upstream são conferidos. Publicação com mais de 30 minutos, páginas de referências diferentes ou resultado integral repetido em outro dia não criam uma nova base. O tempo de leitura local nunca torna dados upstream antigos atuais. Personagem ausente não equivale a XP zero. Diferenças exigem todas as bases adjacentes do período; dois snapshots são o mínimo, e 7/30 intervalos exigem 8/31 bases. Valores negativos e zero reais são preservados. Exibimos o intervalo de observação, não o chamamos de XP de ontem; médias usam as horas efetivas entre as coletas.

O laço do WhatsApp não busca rankings. O novo `python -m automation collect-xp` é somente leitura de fontes públicas e escrita de caches: nunca lê inbox, pareia ou envia mensagens; configura apenas o banco/chave de dados e não precisa do token nem da autorização de transporte WhatsApp. Instalar `deploy/zt-xp-collector.service` e `.timer` com o mesmo usuário/ambiente privado do worker, conferir os caminhos e habilitar **somente esse timer** após a implantação revisada. Uma execução coleta um mundo; até 20 mundos acompanhados, TTL/backoff de 15 minutos, bloqueio GuildStats por 6 horas e lease de mundo de 240 segundos; a unidade encerra após 180 segundos. A CLI imprime um resumo controlado de fonte/estado/código HTTP/classe do erro, sem URLs ou conteúdo. Falha em todas as fontes tentadas termina com código 1; sucesso parcial é informado, e backoff/nenhuma coleta devida termina normalmente. Não fazer consultas de ranking dentro do worker existente. Sem instalar o coletor, a UI informa que aguarda dados; não inventa um histórico.

Na prévia e no bom dia, os extras `exp_mundo`/`exp_guild` usam o mesmo cache. GuildStats recente mantém números e a data real da consulta. Cache antigo vira um aviso individual datado; TibiaData só mostra variação entre coletas com horários/fonte explícitos. `transfer` indisponível recebe aviso, nunca “não houve transferências”. Essas três falhas não bloqueiam os 13 blocos básicos válidos. Falha em qualquer bloco básico ainda interrompe a geração. As fontes derivadas registram a hora do cálculo e os tempos upstream de entrada separadamente; nenhuma data original é renovada.

HTTP 400 na prévia mostra o motivo controlado do servidor (tamanho limitado, texto puro), em vez de sugerir indevidamente trocar código de recuperação. Só a recuperação mantém esse aviso específico. A política de expiração/envio e os estados aceito/incerto não foram alterados: não reenviar um bom dia vencido automaticamente. Logs novos de falha de geração/troca de revisão guardam referência, versões, classe do erro e decisão de retry, sem texto da mensagem, credenciais ou IDs de sessão.

O código não libera o Cloudflare: acesso autorizado ao histórico exclusivo do GuildStats continua necessário quando a origem responde 403. Não há rotação de IP, solução automática de desafios nem importação de sessões. Reversão: parar o coletor, restaurar os arquivos revisados anteriores e manter o banco/chaves; as tabelas novas são aditivas. Não apagar `rank_history`, identidades, sessões ou envios aceitos/incertos.

### Fonte adicional TibiaRise

O coletor também consulta os endpoints públicos utilizados pela interface TibiaRise: `/api/character/{nome}?page=1|2` e `/api/experience-by-world/{mundo}/daily|weekly|monthly`. Não é uma API contratada/documentada: formato, cobertura e disponibilidade podem mudar. A fonte é exibida como **TibiaRise**, sem presumir equivalência com o GuildStats. Rankings têm até 100 entradas; nomes duplicados na lista são omitidos sem somar nem escolher um ganho arbitrário.

`xp_rise_cache` guarda dados cifrados e uma fila de até 200 nomes públicos. A primeira consulta de XP enfileira o personagem sem HTTP no laço do WhatsApp. Cada `collect-xp` busca no máximo um personagem (duas páginas) e um mundo (três períodos), além da coleta de mundo já existente. Após a atualização, uma próxima consulta aproveita o cache. Sucesso aguarda seis horas; falha aguarda quinze minutos. Solicitações dos últimos sete dias são atualizadas; entradas sem solicitação por sessenta dias são removidas. Leases impedem sobreposição de coletas.

Datas e intervalos upstream são preservados. São necessárias 31 medições consecutivas para trinta intervalos completos; lacunas não viram zero. Ganhos negativos são mantidos e precisam coincidir com as diferenças de XP total. Os relatórios individuais usam uma única fonte: GuildStats válido e atual tem prioridade mesmo quando o TibiaRise diverge; se estiver indisponível para o personagem, o relatório inteiro usa TibiaRise. Dados salvos do GuildStats não são mesclados às datas das medições TibiaRise. TibiaData continua sendo coletada, mas não preenche os relatórios individuais. A evolução mostra barras proporcionais, perdas com sinal e caveira e zero sem barra; a fonte por extenso e a última data ficam em um único rodapé, sem o bloco técnico superior. O xptop também identifica somente a fonte selecionada na legenda. Registros antigos podem continuar datados, mas não permitem projeção; os dois personagens de um duelo precisam de períodos comparáveis. `rank_history`, `xp_totals`, sessões e agendamentos permanecem intactos. O resumo da CLI inclui `tibiarise` e distingue falha total de sucesso parcial.

Validação offline: `python -m unittest test_tibiarise test_xp_sources test_commands test_botajustes`. Para testar manualmente sem envio, preencher uma solicitação pública no cache e executar somente `collect-xp`; nunca usar o worker/tick ou `!bomdia teste` para essa verificação.

No bom dia automático, os rankings diários voltam a mostrar somente o título e os ganhos, sem rodapés técnicos de fonte, horários UTC ou duplicações descartadas. A origem e os intervalos exatos permanecem na proveniência interna. Uma guild com cobertura incompleta recebe apenas “Ranking parcial: N de M membros com dados”; nenhum membro ausente é contado como XP zero. Período diário antigo conserva uma data curta no título, e variações TibiaData entre coletas não são renomeadas como XP diário. Essa apresentação não altera o gerador manual nem amplia a cobertura pública do ranking.

### ZenRows opcional no coletor de XP

Os rankings GuildStats podem seguir a ordem **ZenRows → GuildStats direto → TibiaRise**. A primeira resposta só vence depois da validação da tabela; erro HTTP, timeout, página de desafio ou tabela inválida passam à leitura direta. A identidade dos dados continua GuildStats. Esta etapa cobre apenas `/top-experience` (0, 7 e 30 dias): não inclui transferências, histórico individual exclusivo nem amplia o ranking para todos os membros de uma guild.

O cliente fica desligado por padrão e não lê a chave na criação do serviço ou nas respostas dos comandos. A ativação administrativa exige `ZENROWS_ENABLED=1` e `ZENROWS_API_KEY_FILE` apontando para arquivo absoluto **fora do repositório**, com até 512 bytes ASCII e sem quebras de linha internas. A chave deve ser instalada separadamente, legível somente pelo administrador/usuário do serviço, nunca em Git, pacote, URL apresentada ou log. Exemplo de configuração ainda desligada:

```ini
ZENROWS_ENABLED=0
ZENROWS_API_KEY_FILE=/etc/zt-automation/zenrows-api-key
ZENROWS_DAILY_REQUEST_LIMIT=6
ZENROWS_WORLDS=Rasteibra
```

`ZENROWS_WORLDS` restringe o piloto a nomes separados por vírgulas; vazio permite os mundos acompanhados dentro do teto global. O limite padrão é **seis tentativas por dia UTC**, configurável entre 0 e 1000 (0 desliga os pedidos pagos). `zenrows_budget` contabiliza cada tentativa antes da rede em transação SQLite; reinícios e processos concorrentes não renovam a cota. `zenrows_retry` impede nova tentativa da mesma URL por seis horas. Erros 401, 402 ou 429 impõem ainda pausa global de pelo menos uma hora, inclusive ao virar o dia. Não há repetição automática nem recarga de créditos.

O teto é de chamadas, **não de gasto financeiro**: `mode=auto` pode escalar o custo por resposta segundo as regras do fornecedor. Confirmar saldo/limites antes de ativar; referência: [ZenRows Fetch a Page](https://docs.zenrows.com/api-reference/fetch/fetch-a-page). O transporte mantém TLS, não segue redirecionamentos do endpoint autenticado, limita HTML a 6 MB e usa timeout de 20 segundos com prazo de leitura de 25 segundos. Falhas expõem somente mensagens controladas, sem URL/chave/corpo remoto. A unidade do coletor passa a ter timeout de 180 segundos e seu lease de mundo é de 240 segundos; não alterar o worker de envios.

Testes totalmente offline: `python -m unittest test_zenrows test_xp_sources test_tibiarise`. Ativar o cliente e testar uma chamada real são etapas administrativas separadas; os testes usam somente chave sintética e não chamam ZenRows/WhatsApp.

### Apresentação do duelo

`!duelo` mostra dois blocos com emoji da vocação, nome, nível e XP do último intervalo, de 7 dias e de 30 dias. A conclusão tem uma linha; dados antigos, incompletos ou períodos/fontes diferentes impedem projeções e recebem um aviso curto. Os modelos existentes mantêm `{nome1}`, `{nome2}`, `{tabela}` (agora os blocos) e `{resultado}`. A seleção de fontes e os cálculos não mudam.


### Consultas do Assistente Tibiano

`POST /v1/assistant/command` aceita `{text,mundo,personagem}` com a identidade de instalação (`known`), sem exigir liberação ou conexão WhatsApp. Serve apenas help, duelo, evolucao/evo, precocoin/tc, pt/party, char/personagem, online e xptop. Reutiliza Bot/XPProvider e os modelos do scope `assistente`; modelos antigos de char/online mantêm suas variáveis. Não chama transporte nem GroupConfig. O limiter por instalação continua ativo e até quatro consultas executam simultaneamente; corpo e resposta têm limites e campos privados são recusados.

O app usa um adaptador Python com DPAPI e nunca recebe a chave ZenRows. Comandos de texto conhecidos não gastam chamada de IA e falhas não geram estimativas pela IA. Esta integração é somente no chat de texto; a voz existente não muda. Configuração e alertas dos grupos permanecem em Mensagens.
