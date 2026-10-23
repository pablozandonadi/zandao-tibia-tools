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

Recurso só de envio: o servidor consulta a lista pública da guild e a ficha pública dos membros (TibiaData) a cada minuto pelo mesmo `tick` do worker. Level up vem da lista de online do mundo (atual, a mesma fonte do UP Level do app) e não da lista da guild, que a TibiaData entrega com level atrasado; a guild só diz quem é membro e é renovada a cada 15 min. As fichas (mortes) são conferidas em rodízio entre os membros online e manda **uma mensagem por evento** ao grupo escolhido. Nada do que os membros escrevem no grupo é lido; o bom dia segue pelas rotinas diárias.

- **Objeto `watch`** (até 3 por instalação): `guild`, `milestone` (level up a cada N níveis: 1 = todo level, padrão; 50 = só em 100, 150, 200…), `deaths`, `ups`, `hourlyCap` (teto de avisos por hora; 0 = sem limite, padrão), `perMinute` (ritmo de envio de 1 a 120 por minuto, padrão 3), `connection`, `destination`. API: `GET/POST /v1/watches`, `PUT/DELETE /v1/watches/{id}`; mesmas regras de dono, conexão ativa e grupo autorizado das rotinas.
- **Sem retroativo:** a primeira varredura só memoriza os levels; mortes anteriores à criação do alerta são ignoradas. Cada evento tem chave única (`up:nome:marco`, `death:nome:horário`), então nunca repete, mesmo se o personagem perder e recuperar o level.
- **Proteções do número:** no máximo 3 mensagens por minuto e o teto por hora configurado; aviso que não coube e passou de 3 h expira em vez de chegar atrasado. Envio registrado antes do despacho: falha conhecida vira `failed`, resposta duvidosa vira `uncertain` e nunca é repetida. Revogar a conexão cancela a fila.
- **Conteúdo:** nomes vindos do jogo perdem `*`, `_`, `~`, crase e quebras de linha antes de entrar na mensagem. Texto do evento é cifrado no banco como os demais conteúdos.
- **Falha fechada:** guild vazia ou fonte fora do ar não gera evento nem apaga a memória de levels.
- **Implantação:** atualizar o checkout da VM (`zt-deploy.sh`) cria as tabelas `watch_*` sozinho; nenhuma unidade systemd nova. Testes: `python -m unittest test_watch` em `server/message-automation`.
