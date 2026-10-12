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

Implementação validada com 282 testes em cópia limpa. O primeiro push foi recusado pelo GitHub: a credencial OAuth usada pelo Git não tem escopo workflow. Nenhuma branch develop ou Release Beta foi publicada por essa tentativa. Para autorizar a publicação, o usuário pode executar no terminal: gh auth login --hostname github.com --git-protocol https --web --scopes workflow. Após autenticar: gh auth setup-git. Não grave tokens em arquivos do projeto.

O commit preparado está na branch develop da cópia temporária %TEMP%\zandao-beta-pipeline-20261012. A fonte compartilhada continua na sua branch original. Antes de retomar, conferir se origin/main ou origin/develop recebeu alterações e integrar sem sobrescrever trabalho de outro agente. Só depois enviar develop e acompanhar o workflow até terminar.
