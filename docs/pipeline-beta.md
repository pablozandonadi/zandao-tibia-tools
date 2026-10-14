# Beta e estável

A pasta principal é compartilhada pelo Codex e Claude. Não é necessário criar outra pasta permanente para desenvolver. As branches no GitHub representam o destino da publicação; não são pastas adicionais para o usuário.

- develop: cada push de código dispara publish-beta.yml. Testes, PyInstaller e Inno Setup rodam no Windows do GitHub. Instalador e portátil são publicados como prerelease, sem alterar a última release estável.
- main: mantém o workflow existente publish-release.yml, que publica quando versao.py muda. Não aumente a versão em main para testar; isso pode liberar uma versão aos usuários.
- Para liberar uma mudança: validar a Beta, integrar o código aprovado em main, aumentar VERSAO_APP e adicionar docs/releases/vX.Y.Z.md. O fluxo atual recompila em main: ainda não promove o mesmo binário da Beta. Não faça merge indiscriminado de outras mudanças pendentes.

O instalador Beta usa identidade, pasta e atalhos próprios: %LOCALAPPDATA%\Programs\Zandao Tibia Tools Beta. Os módulos atuais salvam dados ao lado do executável; por isso Beta e estável mantêm dados separados. O Beta começa vazio. Dados de produção não são copiados automaticamente.

canal_build.json é gerado fora da fonte e incluído no executável. Identifica o canal e a versão X.Y.Z-beta.execução.tentativa. A fonte compartilhada continua com VERSAO_APP estável. Não use variável de ambiente para trocar o canal de uma instalação.

O atualizador estável consulta releases/latest e aceita somente ZandaoTibiaToolsSetup.exe. O Beta consulta as 100 releases recentes, filtra prereleases beta e aceita somente ZandaoTibiaToolsBetaSetup.exe. Ambos usam o botão existente Baixar e instalar: baixa o pacote, abre o instalador e fecha o app. O usuário ainda confirma as telas do instalador.

Primeiro uso: baixar e instalar ZandaoTibiaToolsBetaSetup.exe da primeira release Beta. Nas próximas versões, usar o aviso automático ou Configurações > Procurar atualização agora. Testar dados persistidos e atalhos após a segunda atualização. Instalar e atualizar no Windows real é uma validação adicional aos testes automatizados.

Build local de teste:

    ./instalador/gerar_instalador.ps1 -Canal beta -BetaBuild 1.1 -PastaBuild "$env:TEMP/zandao-beta"

Durante desenvolvimento, executar python zandao_tibia_tools.py evita compilar a cada ajuste, mas essa execução usa os dados da pasta da fonte, não os dados das instalações. Não teste gravações com dados importantes sem backup.

## Estado da ativação (12/10/2026)

O usuário autorizou GitHub CLI com escopo workflow. A branch develop foi publicada; primeira compilação: https://github.com/pablozandonadi/zandao-tibia-tools/actions/runs/38303390412 (commit 156a96c6ea9ced9c2a770d002e2a3b901ee71f18). A fonte compartilhada continua na branch main local, com estas mudanças disponíveis ao Codex e Claude. A main remota mantém a versão estável 1.0.19.

Para próximas Betas, os assistentes devem publicar somente mudanças aprovadas em develop usando uma cópia sincronizada, sem trocar a branch da pasta compartilhada nem enviar todos os arquivos pendentes indiscriminadamente. A cópia temporária desta ativação está em %TEMP%\zandao-beta-pipeline-20261012. Conferir origin/main e origin/develop antes de reutilizá-la.

282 testes passaram em cópia limpa. Um instalador Beta local de validação também foi compilado; a distribuição aos testadores deve usar o pacote oficial gerado pelo workflow. A instalação e a atualização seguinte no Windows real ainda precisam ser testadas pelo usuário.
## Fluxo permanente de análise do usuário

Ao terminar uma mudança no aplicativo, validar e publicar automaticamente a Beta oficial em develop. O usuário autorizou commits e push nessa branch como preparação da Beta. Main e a publicação estável aguardam aprovação. Essa orientação substitui a exigência anterior de aprovação prévia para gerar/publicar a Beta de análise.

O botão “Publicar na versão original”, em Configurações da Beta, representa a aprovação do usuário para promover a Beta instalada. Usa o GitHub CLI autenticado do computador, com permissão de escrita no repositório; credenciais nunca entram no executável. O acionamento informa a tag e o commit registrados no build, executando o workflow dessa tag. Não promove automaticamente a develop mais recente.

O pipeline verifica a prerelease e o commit, exige que a main seja ancestral da Beta (divergência exige reconciliação e nova análise), aumenta o patch da versão estável, gera notas, testa, recompila instalador e portátil estáveis, e somente então faz commit/push em main e publica a release. Não troca a branch da pasta compartilhada. A interface acompanha a execução e só informa conclusão após a publicação dos dois artefatos. Beta local sem commit de origem não permite promoção.

## Integridade e dados por canal (13/10/2026)

O novo build usa LocalAppData/TibiaTudo/beta ou stable para dados e preserva a instalação antiga ao migrar. O atualizador exige hash/tamanho da release e verifica Authenticode por política local do build. CI fixa ferramentas, valida recursos e publica SHA256SUMS.txt, package-manifest.json e sbom.json. Sem certificado do proprietário, a Beta continua explicitamente não assinada. Configure TIBIA_SIGNING_THUMBPRINT / TIBIA_REQUIRE_SIGNATURE para builds assinados. Detalhes, recuperação e limites de teste: docs/instalacao-segura-e-validacao.md.

## Reconciliação após promoção anterior (13/10/2026)

A Beta 32 foi criada paralelamente à promoção da Beta 27 como estável 1.0.22. A promoção da Beta 32 foi corretamente bloqueada por divergência, mas o diagnóstico estava genérico. A develop incorpora agora a main por merge, preservando código e histórico, e a próxima Beta usa base 1.0.22. A Beta antiga permanece bloqueada; analisar e promover a nova Beta. O erro de ancestralidade agora explica a necessidade de reconciliação. A main não é alterada nesta correção.

## Reconciliação automática após cada promoção (14/10/2026)

Causa raiz da divergência recorrente: ao promover, o pipeline gravava o commit "Publicar Beta aprovada como vX.Y.Z" (versao.py e notas da release) só na main. A develop nunca o recebia, então qualquer commit novo na develop depois de uma promoção criava uma Beta divergente da main, e promover essa Beta era bloqueado (Beta 41 após a promoção da Beta 39 como 1.0.24). Antes era preciso fazer o merge à mão.

Agora o último passo do job original, "Devolver a promoção para a develop", executa `python instalador/promover_beta.py reconciliar <versão>` depois que os pacotes estáveis foram publicados: traz o commit de promoção para a develop (avanço rápido se a develop não andou; senão um merge "Reconcilia estável X.Y.Z na develop") e faz push. A próxima Beta já nasce com a base estável nova (por exemplo 1.0.25-beta.N). O push feito com o token do Actions não dispara outra Beta; a próxima Beta é a do próximo trabalho.

O passo usa continue-on-error de propósito: a release já saiu e o app (publicacao_beta.estado) lê a conclusão geral da execução; uma falha de reconciliação aparece como aviso no log e não transforma uma publicação bem-sucedida em "falhou". Se o aviso aparecer, faça o merge da main na develop antes da próxima Beta, ou `preparar` bloqueará a promoção com a mensagem "Integre a main em develop". Um conflito real (alguém alterou versao.py ou as notas na develop) não é resolvido sozinho: o passo aborta o merge e não envia nada. Os testes ficam em `ReconciliacaoDevelopTests` (test_publicacao_beta.py), com repositórios git locais.

Regra de uso: nunca reaproveite uma Beta bloqueada. Depois de reconciliar, a promoção vale para a primeira Beta nova (base já atualizada), não para a antiga; promover a antiga continua barrado de propósito.
