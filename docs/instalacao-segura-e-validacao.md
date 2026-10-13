# Etapas 2 e 3 — instalação, atualização e Windows

Implementação de 13/10/2026. A etapa 2 possui suporte técnico implementado; assinatura reconhecida depende de certificado que o proprietário informou ainda não ter. A etapa 3 é uma matriz de validação, não uma declaração de aprovação de todos os cenários.

## Atualização

O backend aceita apenas URLs de assets do repositório oficial/canal, guarda os metadados da release e exige SHA-256 e tamanho divulgados pelo GitHub. O download usa diretório temporário exclusivo, arquivo parcial, limite de 256 MiB, limites de tamanho e validação do executável. Redirecionamentos são restritos aos hosts GitHub usados em release assets. Qualquer erro remove o pacote temporário e impede a execução. Uma tentativa interrompida pode ser repetida. O instalador é revalidado imediatamente antes de executar.

SHA-256 conferido com a mesma API da release detecta corrupção/troca de bytes, mas não é uma raiz de confiança independente do GitHub. Authenticode usa WinVerifyTrust do Windows. Quando assinatura é obrigatória, o certificado deve estar na lista de fingerprints aprovada no build. O modo de análise sem certificado permite somente arquivos realmente não assinados ou assinaturas válidas, mantendo digest/tamanho obrigatórios. Assinatura inválida nunca é aceita.

Download oficial de Beta 27 testado em Windows 11: tamanho e digest aprovados, arquivo não executado nesse teste. A API nativa também validou um bootstrap Microsoft assinado; conferiu assinatura e extraiu fingerprint. Essa prova não substitui teste com certificado próprio do projeto, ainda indisponível.

## Build e publicação

- Python 3.14.7 no CI, Inno Setup 6.7.1 e Actions fixadas por commit.
- Dependências diretas/transitivas com versões e hashes PyPI em requirements-bootstrap.lock e requirements-build.lock; sem isolamento de build que baixaria dependências não fixadas.
- Allowlist de recursos web/sons/ícone, catálogos públicos selecionados e validação de layout do pacote. Arquivos conhecidos de dados privados/cache não são permitidos em nenhuma subpasta. Não se trata de classificação semântica de todos os bytes.
- package-manifest.json contém hash e tamanho de cada arquivo, versão/canal/commit. Não é autoassinado; hashes da release vinculam o ZIP final. sbom.json é inventário simples de dependências, não certificação de vulnerabilidades nem SBOM CycloneDX completo.
- Releases publicam instalador, portátil, SHA256SUMS.txt, manifesto e inventário. Pacotes verificados antes de publicar.
- Assinatura: instalador/assinar.ps1 usa SignTool do SDK, certificado pelo thumbprint, SHA-256 e timestamp; exige assinatura válida e publicador esperado. O app é assinado antes do manifesto/Inno, e o instalador depois de compilado.
- Configure TIBIA_SIGNING_THUMBPRINT e provisione o certificado no runner de assinatura; TIBIA_REQUIRE_SIGNATURE=true bloqueia build sem certificado. Nenhum PFX, segredo, senha ou chave privada entra na fonte ou pacote. Não foi criado certificado autoassinado.
- O bootstrap WebView2 precisa de assinatura válida da Microsoft antes de executar. Se WebView2 não ficar disponível, o instalador falha antes de substituir os arquivos do app.

Referências: [WinVerifyTrust](https://learn.microsoft.com/en-us/windows/win32/api/wintrust/nf-wintrust-winverifytrust), [SignTool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool), [assets GitHub](https://docs.github.com/en/rest/releases/assets?apiVersion=2022-11-28).

## Dados e recuperação

Build instalado/portátil guarda dados em %LOCALAPPDATA%/TibiaTudo/beta ou stable. Código-fonte continua usando sua pasta de projeto. Recursos públicos ficam na instalação e podem ser lidos mesmo quando não é possível gravar ao lado do EXE.

Na primeira execução do novo build, arquivos privados conhecidos e sons importados da instalação de origem são copiados somente quando o destino não existe. Os originais ficam intactos, e a migração tem marcador para não importar de novo. Não se copiam dados de Beta para estável, caches ou diretórios de outros programas. Duas cópias do mesmo canal usam o mesmo diretório; instância única impede dois escritores e solicita restaurar a janela já aberta.

Antes de abrir o instalador de atualização, o app guarda EXE, bibliotecas e catálogos da versão anterior em recovery/ sob o diretório do canal; dados pessoais não entram nesse snapshot. Uma atualização pendente é registrada e a próxima abertura indica completed/interrupted no arquivo local. Não há rollback automático de arquivos parcialmente instalados.

Roteiro de recuperação: sair pelo menu da bandeja; preservar/backup da pasta de dados do canal; reinstalar o instalador oficial anterior (conferindo seus hashes) na mesma pasta; reabrir e confirmar os dados. Se for necessário restaurar do snapshot, conservar primeiro a instalação falha e recuperar EXE, _internal e catálogos daquela mesma versão. Não misturar bibliotecas de duas versões. Uma versão antiga que usava dados junto do EXE precisa de restauração explícita dos dados mais recentes; os originais migrados são apenas a fotografia anterior à migração.

## Matriz de validação

| Cenário | Evidência / estado |
|---|---|
| Suite de domínio e regressões | 408 testes em venv limpo Windows/Python 3.12; CI repetirá com Python 3.14.7 |
| Dependências com hashes | Instalação completa em venv novo aprovada |
| Pacote adulterado/truncado/HTML/excessivo | Tests impedem execução e limpam temporário |
| Falha de rede e repetição | Tests com rede simulada e lock liberado após falha |
| Download oficial e assinatura Windows | Teste nativo descrito acima |
| Publicador errado/assinatura obrigatória ausente | Tests simulados bloqueiam; certificado próprio pendente |
| Migração de dados, canal e sons | Tests com arquivos artificiais preservam origem e dados existentes |
| Manifesto/layout/private files | Tests recusam conteúdo extra/privado e bytes modificados |
| Instância dupla | Aprovada também no executável oficial Beta 32: segunda instância encerrou com código zero e primeira permaneceu |
| Snapshot rollback | Test artificial preserva versão antiga sem dados privados |
| Abertura da janela Windows 11 | Cópia temporária abriu, confirmada no inventário de janelas; sem dados reais |
| Captura/ações de UI | Home da Beta oficial 32 renderizada e conferida; usuário interrompeu por Esc a ação seguinte. Demais páginas e bandeja pendentes |
| Instalação primeira/segunda atualização | Aprovadas com payloads oficiais Beta 27 e 32, instaladores de AppId exclusivo e LocalAppData artificial; compilador de validação local 6.7.3, CI oficial 6.7.1 |
| Windows 10 / WebView2 ausente | Ambiente indisponível; não desinstalar WebView2 do computador do usuário |
| Escala 100/150/200%, modo gadget | Pendente teste visual Windows; escala da UI interna não equivale ao DPI do Windows |
| X/bandeja/restaurar/Sair e timers/overlay recolhido | Testes de controlador existem; smoke real depende de captura/controle autorizado |
| Reinício/suspensão/antivírus | Não simular reinício ou alterar proteção do computador em uso; ambiente dedicado necessário |
| Todos os módulos pela UI | Pendente registrar smoke funcional em Home, hunts, loot, task itens, criaturas, histórico, sets/rodas, classificador, prints, Guild Stats e backup |

Dados de teste devem ser artificiais; não executar organizador sobre prints reais. Falhas da etapa 1 do plano (histórico/backup/screenshots/classificador) seguem como tarefas próprias; esta entrega não declara esses problemas resolvidos.

## Entrega e evidências finais

Beta **1.0.21-beta.32.1**, commit `3ccc276ffc16e9a0f6b64cb8ad08c6abe5db9430`. [Release oficial](https://github.com/pablozandonadi/zandao-tibia-tools/releases/tag/v1.0.21-beta.32.1). Pipeline `38405750183` concluído com sucesso; cinco artefatos publicados. ZIP baixado: SHA-256 `b3aa52b2e104884804117ad8e7221fbb9dec65e372e899eeed3638ea782d8dae`, igual à API da release. Manifesto interno validado arquivo por arquivo.

Teste nativo em Windows 11 build 26100: primeira instalação, atualização, preservação dos arquivos antigos, migração para perfil artificial, inicialização das duas versões e recusa de segunda instância passaram. AppId de validação diferente das instalações reais; o canal estável não foi criado no perfil artificial. Relatório: validacao-windows-resultados.json.

Validação criptográfica real: bootstrap Microsoft assinado retornou Valid e fingerprint; uma cópia adulterada retornou Invalid / 80096010. O instalador oficial não assinado da Beta foi baixado e passou em hash/tamanho; o modo de análise permite NotSigned por decisão explícita de ausência de certificado. Não foi emitida assinatura digital própria.

UI: Home da cópia oficial isolada conferida visualmente. Usuário pressionou Esc e interrompeu Computer Use antes da próxima navegação; nenhum comando de interface foi emitido depois disso. Os demais smoke tests continuam pendentes. Esta entrega não declara a etapa 3 integralmente concluída nem valida Windows 10/DPI/reinício/antivírus sem ambiente dedicado.
