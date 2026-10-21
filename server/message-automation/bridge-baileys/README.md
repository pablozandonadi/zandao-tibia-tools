# Ponte privada alternativa Baileys

Implementação local revisável, **não implantada**. Substitui a ponte Go no mesmo contrato privado; a API, worker, autenticação Google e preferências continuam iguais. Escolher **uma** ponte por implantação/porta, sem operar as duas sobre a mesma sessão. O Docker existente na VM e seu diretório de autenticação não foram alterados nem importados.

## Contrato e persistência

- Node **>=22.13.0** com `node:sqlite`; SDK `@whiskeysockets/baileys` **7.0.0-rc14**, QR `1.5.4`, dependências e integridades fixadas em `package-lock.json`.
- Mesmo loopback `127.0.0.1:8788`, token administrativo em arquivo, comparação constante, rejeição de Origin, corpo máximo 64 KiB. Apenas `/sessions/<id-interno>` com status, pair, resume, groups, send e DELETE. O backend resolve proprietário e ID; o cliente não escolhe sessão ou JID real.
- SQLite separado por conexão interna; credenciais e Signal keys usam BufferJSON do SDK. Transações síncronas FULL/DELETE persistem antes de resolver; app-state keys são reconstruídas com o proto oficial. Não usar o helper multifile em produção. SQL guarda somente autenticação/protocolo, aceite/revogação e IDs/estado de tentativa; sem caixa de entrada, conteúdo enviado ou QR persistidos.
- Sessão inicia desconectada; nenhum diretório é varrido ou reconectado. Somente `/resume` de conexão ativa validada pelo backend reconecta credenciais registradas e consentidas. QR fica em memória por até 30 segundos. Revogação invalida memória, elimina credenciais e encerra socket mesmo se a escrita falhar; falha de persistência exige reconciliação operacional antes de reiniciar a ponte. Não significa recall de mensagem já despachada.
- Destinos são handles HMAC distintos por sessão. Antes de chamar `sendMessage`, falhas retornam `not_started`; depois da chamada, resultado desconhecido é `uncertain`, nunca retry automático. Tentativas são registradas antes do despacho e sobrevivem a reinício. Fake retorna `simulated:true`, nunca enviado real.

## Limite importante do SDK rc14

`syncFullHistory:false` e `shouldSyncHistoryMessage:()=>false` bloqueiam inclusive o bootstrap. Nenhum handler de mensagens/histórico, `readMessages` ou recibo de leitura é usado. O SDK pode receber eventos/acks de protocolo; não existe promessa de zero recebimento ou de invisibilidade. Não confirmar leitura de intimações nem atribuir efeito jurídico.

A fonte oficial rc14 alerta que bloquear todo histórico também pode impedir mapeamentos iniciais LID e prejudicar a conexão. Por isso **pareamento, reconexão e envio reais desta alternativa permanecem sem validação e pendentes de teste controlado autorizado**. Não habilitar histórico implicitamente para contornar esse limite. Os testes são de contrato com sockets sintéticos, não prova de compatibilidade real. Cada jogador precisa aceitar riscos de integração não oficial e eventual bloqueio antes de parear.

## Preparação executável, sem mudar infraestrutura

Em checkout de teste, sem copiar autenticação existente:

```sh
cd server/message-automation/bridge-baileys
node --version
npm ci --ignore-scripts --no-audit --no-fund
npm test
```

Os testes usam SDK importado sem construir socket real, SQLite temporário e HTTP loopback; não usam conta, QR ou WhatsApp reais. `npm start` não faz parte do teste. O CI executa Node 22; a validação local disponível usa Node 24.

Para preparar implantação futura, revisar o runbook principal primeiro. O padrão é `BRIDGE_MODE=fake`; a API também deve permanecer fake. Se um operador aprovar futuramente a troca, usar checkout e armazenamento **novos e exclusivos**, token fora do repositório/estado e usuário sem root. Revisar override da unidade existente, preservando sandbox, `LimitCORE=0`, permissões e `EnvironmentFile`:

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/node /opt/zandaotools/server/message-automation/bridge-baileys/main.mjs
```

Esse trecho é uma proposta de override; não foi instalado ou iniciado. Não expor porta 8788, não criar um segundo serviço concorrente. Node/dependências ficam somente no servidor, fora do instalador desktop.

O modo real exige simultaneamente `BRIDGE_MODE=real`, `BRIDGE_ENABLE_REAL=I_ACCEPT_UNOFFICIAL_WHATSAPP`, aceite do proprietário e diretório privado em **mount Linux LUKS/dm-crypt comprovado via mountinfo + UUID CRYPT-LUKS**. Chaves fora do volume e backup. Sem isso a inicialização falha. O diretório novo recebe marcador próprio; diretório não vazio sem marcador é rejeitado, sem ler/importar seu conteúdo. Gate não é flag declarativa. Em container o mount pode não ser verificável: não enfraquecer a checagem; preparar execução compatível antes de habilitar real.

Google Client ID e domínio HTTPS ainda estão pendentes. Login real, implantação, pareamento, envio de teste e ativação de agenda exigem configuração e aprovações separadas. Nada disso foi executado.

## Sessão legada, backup e restore

A sessão já pareada da VM **não pertence automaticamente ao primeiro usuário**. Migração dessa sessão não está implementada: exige parada explícita do processo antigo, confirmação do dono, procedimento de conversão revisado e teste autorizado posterior. Nunca apontar esta ponte ao auth antigo nem iniciar duas bibliotecas sobre a mesma conta/storage. Jogadores novos recebem IDs e sessões novos isolados pelo backend.

Para backup/restore, parar API/worker/ponte antes de copiar SQLite; manter rede da ponte bloqueada até reconciliar conexões revogadas no backend. Backups externos devem ser cifrados, com retenção limitada e chave separada. Não restaurar sessão revogada nem reconectar por varredura. Uma falha de tombstone SQL é fail-stop em memória, mas não prova revogação durável: corrigir o armazenamento e reconciliar a revogação antes de reiniciar.

Fontes primárias: [SDK rc14](https://github.com/WhiskeySockets/Baileys/tree/v7.0.0-rc14), [configuração e alerta de histórico](https://github.com/WhiskeySockets/Baileys/blob/v7.0.0-rc14/src/Socket/socket.ts), [persistência recomendada](https://github.com/WhiskeySockets/docs/blob/main/docs/authentication/session-management.mdx), [histórico](https://github.com/WhiskeySockets/docs/blob/main/docs/advanced/history-sync.mdx).
