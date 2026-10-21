# Mensagem automática — serviço preparado, sem implantação

Esta pasta contém API, agendador, portal Google e ponte privada. **Nada aqui foi implantado, pareado ou enviado ao WhatsApp nesta entrega.** `fake` é o padrão. Nesse modo, a execução termina como `simulated`, nunca como mensagem enviada. O desktop mantém Mensagem do dia e World Board manual intactos; sua nova subseção permite configurar, pré-visualizar, exportar JSON e abrir este portal no navegador do sistema.

## Comportamento e limites

- Qualquer usuário Google autorizado pelo cliente OAuth configurado pode ter sua própria conexão. O servidor deriva o dono de `issuer` + `subject`; não aceita dono, JID, caminho de sessão ou snapshot do cliente. Quotas iniciais: 1 conexão e 5 assinaturas por usuário, 50 conexões/500 entidades de cada outro tipo no serviço, 60 solicitações autenticadas/minuto, JSON até 32 KB e mensagem até 16 mil caracteres. Capacidade gratuita não é ilimitada.
- O portal usa o botão oficial Google Identity Services. ID token só em memória, API Bearer RS256/JWKS, audiência exata, emissor, sub, expiração e iat obrigatórios; `azp` deve coincidir quando presente. Sem client ID/configuração válida, acesso protegido falha fechado. `GOOGLE_ALLOWED_DOMAIN` opcional restringe `hd` e email verificado; vazio permite contas Google conforme público do OAuth. O portal mantém nonce e época do login pendente apenas em memória; `/auth/check` verifica assinatura/claims antes de comparar o nonce esperado. A credencial só é assumida após essa verificação; logout invalida a época e impede callback tardio de reabrir a sessão. O nonce não torna o bearer descartável nem elimina replay de token roubado até sua expiração. Não há login Google dentro do WebView, senha, cookie de autenticação, token em localStorage/URL ou usuário de desenvolvimento exposto. O login real ainda depende do client ID e domínio do titular.
- Exportar JSON não transfere conta nem autenticação. O jogador importa o arquivo no portal autenticado e revisa antes de salvar/ativar; dados do arquivo não entram na URL. Preferências locais do desktop compartilham o perfil do navegador/WebView, não representam isolamento de contas cloud.
- Nove variáveis, treze blocos e sete extras seguem o contrato puro em `mensagem_automatica_core.py`. Formatação automática é independente; não consome a fila da frase manual. Coleta só fontes selecionadas, força consultas e registra fonte/horário/data. Extras reaproveitam bytecode em namespace privado, também em aplicativo frozen, sem ler fontes `.py` ou modificar módulos globais. Falha/velho/incompleto não vira ausência. Valores manuais dinâmicos precisam de `manualDate` igual à data do Tibia; uma configuração manual não ganha validade diária automaticamente.
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

`demo` usa dados sintéticos locais, geração às 12:00 e despacho falso às 12:10; imprime somente modo, estados e contagem. Não carrega conta ou dados de usuários. Testes API usam chave RSA sintética e client JWKS injetado somente no teste. `test_portal.cjs` intercepta toda rede Google/API; `test_mensagem_automatica.py` na raiz testa todos os campos/extras e suporte frozen sem fonte. CI separada `test-message-automation.yml` executa core/demo/portal/Go e cross-build ARM64 sem segredos.

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

4. Configurar login após o titular fornecer domínio/client ID. Criar cliente OAuth **Web** no Google Cloud Console com origem JavaScript HTTPS exata do portal, consentimento/público apropriados e políticas exigidas; não publicar OAuth por efeito colateral. Colocar client ID público em `GOOGLE_CLIENT_ID` e origem em `AUTOMATION_ORIGINS`, sem barra final. GIS é servido em `/portal`; JWKS/emissor Google são fixos por padrão no runtime. Opcional `GOOGLE_ALLOWED_DOMAIN`. Nenhuma senha/chave privada Google é necessária para GIS. Referências: [GIS botão](https://developers.google.com/identity/gsi/web/guides/display-button), [Google OIDC](https://developers.google.com/identity/openid-connect/openid-connect). Desktop usa `AUTOMATION_PORTAL_URL=https://SEU-DOMINIO/portal` no ambiente do processo e abre navegador do sistema; não inserir token nessa variável.
5. Configurar proxy HTTPS para `127.0.0.1:8787`, TLS válido, limite de corpo **32k**, limites de conexão/requisição e origem exata. Não registrar Authorization, cookies, corpo, query ou QR no proxy. Permitir público somente HTTPS; SSH restrito ao IP administrativo; 8787/8788 e bancos nunca públicos. Saída precisa atender fontes públicas, Google JWKS e, quando autorizado, WhatsApp. Validar destinos reais antes de restringir egress; não inventar allowlist incompatível. Sincronizar relógio da VM.
6. Instalar unidades com API/worker sem root, código protegido e diretórios de estado específicos. Units não concedem OCI IAM. Na pasta do serviço:

```sh
sudo install -m 0644 deploy/zt-automation-api.service deploy/zt-automation-worker.service deploy/zt-automation-worker.timer deploy/zt-whatsapp-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemd-analyze verify /etc/systemd/system/zt-automation-api.service /etc/systemd/system/zt-automation-worker.service /etc/systemd/system/zt-whatsapp-bridge.service
# Somente depois de revisar env, mounts, domínio e login:
sudo systemctl enable --now zt-automation-api.service zt-automation-worker.timer
```

O modo inicial continua fake e não precisa iniciar ponte. Executar a demo e validar API/portal com OAuth de teste autorizado; revisar prévia e logs antes de solicitar uso real. `deploy/logging.json` permite apenas eventos operacionais controlados; nunca usar debug/protocol dumps. Definir retenção de logs de 14 dias no destino operacional e backups cifrados diários de 7 dias. Não alterar retenção global de outros serviços por efeito colateral.

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

Conta/região/quota/volume Oracle e autorização de infraestrutura; domínio/TLS e client ID Google; confirmar mundo/horários/fuso; aprovação individual de riscos/pareamento; grupo e texto do teste real; verificação controlada de ausência de recibos de leitura e ativação final. VM, OAuth, firewall, TLS, systemd e WhatsApp não foram alterados por esta entrega. A documentação não constitui confirmação de leitura de mensagens ou intimações.

Alternativa privada Node/Baileys e limites de migra��o: [bridge-baileys/README.md](bridge-baileys/README.md). Escolher somente uma ponte; nenhuma sess�o legada � adotada automaticamente.
