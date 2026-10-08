# Zandao Tibia Tools

Um programa só para quem joga Tibia, com sete abas:

| Aba | O que faz |
| --- | --- |
| **Embuimentos** | Calculadora dos embuimentos Powerful (mesmas regras da planilha `calculadora_embuiment`). Você digita os preços, sem IA e sem ler prints. |
| **Hunt Analyser** | Loot Split + Tibia Damage juntos: cola os textos do Tibia e sai a análise no estilo do hunt-analyser.com. |
| **Histórico** | Toda hunt analisada fica salva neste PC. Dá para filtrar por personagem, exportar e importar. |
| **Ferramentas** | Boss e criatura do dia, Rashid, server save, calculadora de Shared XP e "Quando eu upo?". |
| **Timers** | Timers de áudio: uma tecla apertada no Tibia começa a contagem e o app toca um som no fim (funciona minimizado). |
| **Prints** | Organiza as screenshots do Tibia em `Personagem / Tipo (/ Mês)`. |
| **Configurações** | Meus personagens, backup de tudo (exportar/restaurar) e versão/atualização. |

Os projetos antigos (`zandao embuimentos`, `tibia-screenshot-organizer-1.0.3`, `macro ek`, `divisor de loot`, `tibiadamage`) continuam
funcionando separados. Esta pasta tem as suas próprias cópias.

## Hunt Analyser

1. Com o programa aberto, clique em **Copy** no Tibia no **Party Hunt Analyser**, no **Hunting Analyser** (a sua
   hunt: XP, monstros e itens) e no **Input Analyser** (Received Damage), um depois do outro. Depois clique em
   **📋 Colar do Tibia**: os 3 cards são preenchidos de uma vez. O Windows só guarda a última cópia, então o
   programa guarda cada texto do Tibia copiado enquanto está aberto (só textos do Tibia; qualquer outra cópia é
   ignorada e nunca é salva). Também dá para colar direto nas caixas (Ctrl+V).
2. Em **Seu personagem**, escolha quem é você (o Hunting Analyser fica ligado a esse membro da party). Clique em
   **⚙** para cadastrar seus personagens: o app confere no tibia.com e guarda nome, level, vocação e mundo (em
   `meus_personagens.json`). Dá para ter vários e trocar a qualquer momento; o escolhido fica salvo.
3. A análise sai sozinha:
   - **Resumo da hunt**: duração, XP e Raw XP (e por hora), balance, lucro por membro (e por hora), balance/h, top dano, despesas.
   - **Membros da party**: dano e cura (com % e por hora), loot, supplies, balance, **Profit/h** (o balance de cada
     um por hora, antes da divisão) e quanto cada um recebe ou paga.
     Clique no nome para tirar alguém da divisão.
   - **Distribuição dos pagamentos**: os `transfer N to Fulano` com botão de copiar e a caixinha **Pago?**.
   - **Detalhes por membro** e **Monstros mortos** (com imagem).
   - **Dano recebido**: distribuição por elemento (o Damage Input é o dano real; sem ele, estima pelos ataques
     da TibiaWiki), **proteções recomendadas** (botão leva direto para a aba Embuimentos) e **melhor elemento
     para atacar** (pelas resistências da TibiaWiki), com a ficha de cada monstro.
   - **🧥 Itens recomendados**: todos os equipamentos do set (capacete, armadura, calça, botas, escudo/spellbook/
     quiver, amuleto e anel) que protegem do dano da hunt, filtrados pela vocação e pelo level do seu personagem
     (dá para trocar a vocação e o level ali mesmo). Aba **Esta hunt** ordena por quanto cada item reduz do dano
     total (pesando cada elemento pela parte do dano); as outras abas ordenam por um elemento só. Dados da
     TibiaWiki, baixados na primeira vez e guardados em `cache_itens.json`.
4. **Despesas extras** (boat, hireling...): quem pagou é reembolsado na divisão. **Copiar resumo** gera o texto para o Discord.
5. **Seu personagem nesta hunt** (seção que abre e fecha): marque as **preys** (até 3: tipo, estrelas com o bônus
   calculado e a criatura), os **charms** (majors e minors, nível 1, 2 ou 3 e a criatura) e a **roda** (Wheel of Destiny)
   que você usou, escolhida entre as que você cadastrou em Configurações. Não muda nenhum número
   (o que você cola do Tibia já vem com prey e charms); serve para lembrar, ao comparar hunts, por que uma rendeu
   mais. Uma hunt nova começa com as preys e charms da sua última hunt. Hunts antigas ficam como "não informado"
   (diferente de "sem prey") até você marcar.
6. **Dano recebido, proteções e elemento para atacar** e **Itens recomendados** ficam em seções que abrem e fecham
   (fechadas por padrão, para a tela não ficar enorme).

As contas do Loot Split são as mesmas do `divisor de loot` (TibiaLootSplit). A parte de dano é o Tibia Damage
portado para Python, com duas correções: os embuimentos de proteção certos (Dragon Hide = fogo,
Cloud Fabric = energia, Quara Scale = gelo, Snake Skin = terra, Lich Shroud = morte, Demon Presence = sagrado) e o
Damage Input valendo sozinho quando existe (o site misturava com a estimativa da wiki).

As fichas dos monstros vêm da internet (TibiaWiki + TibiaData) só na primeira vez; ficam em `cache_monstros.json`.

## Histórico

Uma hunt só vai para o Histórico quando você clica em **💾 Salvar** (ao lado de **Nova hunt**). Fica em
`historico_hunts.json`, só neste computador, igual ao Zandonadi Radar: cada pessoa tem o seu. Depois de salvar,
qualquer mudança (nome, despesas, quem saiu da divisão, "pago") aparece como "alterações não salvas" até você
clicar em **💾 Salvar alterações**. O Hunt Analyser abre sempre limpo; só o "Seu personagem" é lembrado.

- **Tamanho da party**: filtra Solo, PT 2, PT 3, PT 4 ou PT 5+. **Spawn (monstro)**: só as hunts com aquele monstro.
- **📊 Comparar todas**: todas as hunts do filtro atual (30, 50, quantas forem) numa tabela, uma hunt por linha.
  Clique no título de uma coluna para ordenar e ver a evolução dela no gráfico (com a linha da média). Verde = acima
  da média, vermelho = abaixo; no rodapé, média, melhor e pior. Embaixo, o ranking por jogador somando todas as
  hunts (clique numa coluna para ordenar, maior primeiro). Clique no nome de uma hunt para abri-la.
- **⚖️ Comparar** (lado a lado): marque 2 a 4 hunts e clique em **⚖️ Comparar**. Primeiro vem o **ranking por
  jogador** somando as hunts comparadas (1º, 2º...; o mesmo do "Comparar todas"). As colunas "/h" são a projeção para
  1 hora: uma hunt de 1h17 é dividida por 1,28 e uma de 40 min multiplicada por 1,5, e cada jogador conta só o tempo
  das hunts em que estava. Depois, a tabela normalizada por hora e por membro (lucro, balance, loot, supplies, XP,
  dano e cura) e o **Detalhe por hunt** (cada jogador em cada hunt, abrindo em "Dano / hora"). ★ marca o melhor valor;
  o veredito diz qual hunt rendeu mais, e os avisos dizem quando a party, a duração, o personagem, o spawn ou a
  prey são diferentes.
- Cada hunt mostra a **prey**, os **charms**, a **roda** e o **set** marcados (ou "não informado"); rodas ou sets
  diferentes entre as hunts comparadas geram um aviso (o do set diz quais itens mudam).
- **Abrir** recarrega a hunt no Hunt Analyser (com as transferências já marcadas como pagas).
- **Exportar** gera um `.json` com todas as hunts (ou só as do personagem filtrado).
- **Importar (somar)** traz as hunts de um arquivo exportado, seu ou de um amigo, sem repetir as que você já tem.
  **Importar substituindo tudo** apaga o seu histórico e fica só com o do arquivo.

## Ferramentas

- **Hoje no Tibia** (também no topo do menu lateral): boss boostado e criatura boostada do dia (TibiaData, atualiza
  sozinho depois do server save), cidade do **Rashid** e quanto falta para o **server save** (10:00 de Berlim; o app
  mostra no horário do seu PC).
- **Shared XP**: digite um level para ver com quem ele divide XP, ou os levels da party para saber se o shared
  funciona (o maior pode ser no máximo 3/2 do menor).
- **Quando eu upo?**: quanto falta para o level alvo e quantas horas/hunts, usando a XP/h média das suas hunts salvas
  daquele personagem. Para ficar exato, digite a XP atual da janela Skills do Tibia.

## Instalar

Baixe o **ZandaoTibiaToolsSetup.exe** na última Release do GitHub
(https://github.com/pablozandonadi/zandao-tibia-tools/releases/latest) e rode. Não precisa de administrador,
nem de Python. O programa fica em `%LOCALAPPDATA%\Programs\Zandao Tibia Tools`.

Cada pessoa começa do zero: o instalador não leva histórico, preços nem personagens de ninguém. Ao abrir, o programa
avisa quando sai versão nova e se atualiza sozinho; histórico, preços, pastas e personagens continuam salvos.

O Windows pode mostrar o aviso do SmartScreen ("O Windows protegeu o computador"), porque o instalador não
tem assinatura digital: clique em **Mais informações → Executar assim mesmo**.

## Usar por cima do Tibia

No fim do menu lateral:

- **📌 Fixar por cima**: a janela fica na frente do Tibia, mesmo quando você clica no jogo.
- **Transparência**: deixa a janela de 40% a 100% opaca, para ver o jogo por trás.

Diminua a janela e coloque num canto: com menos de ~760 px de largura, o menu vira só ícones.
As duas opções ficam salvas em `preferencias.json`. Funciona com o Tibia em janela ou em tela cheia sem bordas.

## Rodas (Wheel of Destiny)

Em **Configurações → Minhas rodas** você cadastra cada roda com um nome e o **código do planner** do tibia.com (ou o link
dele, ex.: `K0Y2AgDP4jAQA`); a primeira letra do código é a vocação. **👁 Ver** mostra a roda desenhada pelo **planner
oficial da Tibia**: o app baixa os arquivos dele do tibia.com na primeira vez (precisa de internet; ficam em `cache_roda/`,
no seu PC, e não vão para o GitHub nem para o instalador) e roda tudo numa caixa isolada, sem acesso aos seus arquivos.
Se não houver internet ou o planner mudar, aparece o código e um botão que abre o planner no navegador. As rodas ficam em
`rodas.json` e entram no backup. Na hunt, a roda escolhida fica salva junto (nome e código), mesmo que você apague a roda
depois.

## Character Set (equipamento da hunt)

Em **Configurações → Meus sets de equipamento** você monta o conjunto que usa: para cada espaço (capacete, amuleto,
armadura, arma, escudo/spellbook/quiver, calça, botas, anel) escolhe o item numa lista da **TibiaWiki** (com filtro por
nome e por vocação) e, se o item tiver vaga de embuimento, escolhe quais embuimentos ele leva. Também dá para listar os
consumíveis (poções etc.). A lista de itens de cada espaço é baixada na primeira vez (precisa de internet) e fica em
`cache_itens_set.json` por 30 dias; os sets ficam em `sets.json` e entram no backup. Nenhum dos dois vai para o GitHub.
No Hunt Analyser, em **Seu personagem nesta hunt**, você escolhe o set usado e abre **👁 Ver o set** para vê-lo dividido em
**Ataque** (arma, anel, amuleto) e **Defesa** (capacete, armadura, calça, botas, escudo). O set escolhido fica salvo junto
da hunt (mesmo que você edite ou apague o set depois) e aparece no Histórico e no comparativo.

O painel **📊 Combat Stats** (no editor e em "Ver o set") soma tudo do set: Armor, Defense, Attack (e ataque elemental),
resistências por elemento, skills (magic level, sword fighting, speed...), leech, crítico, conversão elemental, capacidade
e o que só vem em texto (ex.: Faster Regeneration). Os embuimentos entram com os valores dos **Powerful** da TibiaWiki
(`stats_set.py`; ex.: Void = 8% de mana leech, Vampirism = 25% de life leech, Lich Shroud = +10% de proteção Death). No
comparativo, a tabela **📊 Combat Stats (set, prey, charms e roda)** mostra cada stat lado a lado, com ★ no melhor valor de cada linha.

**Proficiência da arma e Perk Shaping:** ao escolher a arma no set, o app busca na TibiaWiki em português os perks dela
(7 níveis, 1 a 3 opções por nível). Você marca o **nível de proficiência** que tem (começa no 7, sem Maestria), escolhe
**uma opção por nível** (a primeira é o padrão) e, no **Perk Shaping**, troca perks por outras opções com rank de 0 a 10:
embaixo de **cada perk** há o botão **⚒ reshape**, que troca justamente aquele perk (o novo aparece no mesmo lugar, com ícone e
valor). O 1º reshape precisa de 1 nível de proficiência e o 2º precisa de Maestria. O reshape só entra na soma quando você
está usando aquele perk. Os perks que valem sempre (critical
extra damage, critical hit chance, magic level, leech, attack) entram nas linhas normais; os que valem só numa condição
(ex.: "para Death spells e runes") ficam em **Perks da arma**. Os dados ficam em `cache_proficiencia.json` (30 dias).

**Como o Combat Stats calcula (igual ao Tibia):** cada linha mostra de onde vem o valor (Bônus fixo, Equipamento, Embuimento,
Proficiência, Roda, Nível). As **resistências do mesmo elemento se combinam multiplicando** (1 − produto de 1 − cada uma), como o Tibia
mostra (ex.: Physical 5%, 5%, 2% e 5% dão +15,98%). O **crítico** soma o bônus fixo do personagem (+5% de chance e +10% de extra damage, conferido
no Tibia), embuimentos e proficiência. O **Flat Damage and Healing** é o level ÷ 5 mais o "Damage and Healing" da roda. O que o Tibia
mostra na aba Misc (perks de proficiência de uma spell específica e os augments da roda, como "Front Sweep +40% Base Damage") fica junto do
ataque, marcado com o selo **misc**. Não entram ainda: o Attack e o Defence que vêm das skills, e a Mitigation.

**Combat Stats da hunt:** em "Seu personagem nesta hunt" aparece o painel **📊 Combat Stats desta hunt**, somando o set
com a **prey** (XP, loot, dano causado e dano recebido, contra a criatura marcada), os **charms** (efeito no nível
escolhido) e a **roda** (o resumo que o próprio planner oficial calcula, guardado por código em `cache_roda_resumo.json`;
na primeira vez o planner abre escondido para calcular). Embaixo da roda (e no painel) aparecem as **bolinhas**: ● o estágio liberado
de cada revelação (Avatar of Storm, Gift of Life...), ◆ o nível de cada augment e da ressonância das gemas, e ○ ◇ o que ainda não foi liberado.

**Postura (stance):** em "Seu personagem nesta hunt" você marca a postura usada (ex.: Master of Decay para Sorcerer, Blood Rage para
Knight; as da sua vocação aparecem primeiro). O efeito entra no Combat Stats, e o Histórico e o comparativo mostram a postura (e avisam
quando ela muda). Os dados vêm da TibiaWiki (`posturas.py`).

**Classificador de dano:** no Hunt Analyser há a seção **🔎 Classificador de dano**, que abre dentro do app a página da comunidade
([lucasporfz](https://github.com/lucasporfz/classificador)): você cola o server log e o local chat da mesma hunt e vê quanto cada spell fez. É a página
dele ao vivo (precisa de internet); o código não é copiado para o app. O Tibia guarda só as últimas linhas desses logs, então copie
logo depois da hunt.

## Embuimentos

1. Marque à esquerda os embuimentos que vai fazer (dá para filtrar por grupo).
2. Preencha o preço do Gold Token, a taxa de embuir e, no meio, o preço unitário de cada item e do scroll pronto.
   Aceita `4.475`, `4,475`, `4.5k` ou `1.2kk`. Em **Já tenho**, coloque o que já está no seu inventário.
3. O resultado à direita atualiza sozinho: **FAÇA ASSIM**, as 4 rotas (scroll pronto, itens no market,
   6 tokens, 4 tokens + último item) e a comparação do plano inteiro. Use **Copiar resultado** para colar no Discord.

4. **📌 Registrar preços de hoje** guarda os preços que estão na tela (itens dos embuimentos escolhidos, scrolls,
   gold token e blank) com a data de hoje, em `precos_historico.json` (1 registro por dia; registrar de novo no mesmo
   dia troca o valor). Ao digitar um preço, aparece embaixo **▲ mais caro** (vermelho) ou **▼ mais barato** (verde)
   em relação ao último registro de antes de hoje. Clique no nome do item (ou no 📈 do token/blank) para ver o
   gráfico, o menor, o maior e a média, e apagar um registro digitado errado. Entra no backup das Configurações.

Tudo o que você digita fica salvo em `dados_embuimentos.json`. Para adicionar ou alterar embuimentos, edite
`data/imbuements.json`. Só Void, Strike e Vampirism têm rota de token (`has_token: true`).

## Prints

As mesmas opções do Tibia Screenshot Organizer, salvas no `settings.json`. Quem instala começa com as duas pastas em branco; **Usar pasta padrão do Tibia** preenche a pasta de screenshots num clique.

## Timers de áudio

Igual ao TibiaAudio do TibiaVision. Cada timer tem uma **tecla** (clique em "Gravar tecla" e aperte; aceita
Ctrl/Shift/Alt), uma **duração** (minutos, segundos e milissegundos), um **som** (os sons padrão que vêm com o app,
bipes gerados pelo app ou um .mp3/.wav seu) e um **modo**:

- **Reinicia a cada aperto**: apertou de novo antes de acabar, volta do começo.
- **Conta até o fim**: apertar enquanto conta não faz nada; acabou, avisa e espera o próximo aperto.
- **Loop**: um aperto começa a repetir sozinho (avisa a cada volta); outro aperto para.

"Avisar antes de acabar" (também em min/seg/ms) toca o som antes do fim. No card **📍 Barra e alerta no Tibia**
(abaixo do timer que você está editando), cada timer pode mostrar por cima do Tibia (sem dar para clicar: o clique
passa para o jogo):

- um **📢 alerta** em texto: mensagem própria, cor livre, tamanho da letra, **piscar** (fade) nos últimos 1, 2, 3 ou
  5 segundos e a opção de ficar na tela até apertar a tecla de novo;
- uma **▬ barra** correndo enquanto conta, na cor do timer.

Largura, espessura e posição da barra e posição do alerta ficam no mesmo card. **👁 Testar alerta** liga um teste
ao vivo (clique de novo para parar): a mensagem e a barra ficam na tela e mudam junto com o que você ajusta. Cada
opção também tem o próprio botão de teste. **⇩ Importar do TibiaVision** traz os timers e sons dos perfis do
TibiaVision instalado no PC. Funciona com o Tibia em janela ou tela cheia sem bordas e com o app minimizado. Por
padrão só conta com o Tibia (`client.exe`) em foco. O app só confere se as teclas cadastradas estão apertadas: não grava o que é
digitado e não manda tecla nenhuma para o jogo. Configuração em `audio_timers.json`, sons seus em `sons_usuario/`.

## Configurações

- **Meus personagens**: adicionar (conferido no tibia.com), usar e remover. A ⚙ do Hunt Analyser abre aqui.
- **Backup de tudo**: **Exportar tudo** gera um `.json` com histórico de hunts, meus personagens, embuimentos
  (preços, o que já tem, escolhidos), pastas dos prints e fixar por cima/transparência.
  **Restaurar um backup** mostra o que tem no arquivo e, ao confirmar, substitui esses itens (os atuais ficam
  guardados como `<arquivo>.antes-do-backup` na pasta dos dados).
- **Programa**: versão, procurar atualização agora e abrir a pasta dos dados.

## Para desenvolvedores

Mesmo esquema do Zandonadi Radar: Python + **pywebview**, com a interface em HTML/CSS/JS.

| Arquivo | Papel |
| --- | --- |
| `zandao_tibia_tools.py` | abre a janela pywebview |
| `web/index.html` | interface (visual do Radar) |
| `web_api.py` | funções que a página chama (`window.pywebview.api.*`) |
| `embuimentos.py` | cálculo das rotas (testado com os números da planilha) |
| `organizer.py` | organiza as screenshots |
| `hunt.py` | junta Party Hunt + Hunting Analyser + Damage Input numa análise só |
| `loot_core.py`, `solo_hunt_core.py` | cópias do `divisor de loot` (parsing e divisão do loot) |
| `damage_core.py` | Damage Input, distribuição de dano, proteções e ranking ofensivo (porte do Tibia Damage) |
| `monstros.py` | fichas da TibiaWiki/TibiaData, com cache em disco |
| `historico.py` | histórico local, exportar/importar |

```
python zandao_tibia_tools.py      # roda sem gerar o exe
python -m unittest                # testes do cálculo
build.bat                         # testes + gera um exe avulso nesta pasta
```

### Lançar uma versão nova (atualização automática)

1. Aumente `VERSAO_APP` em `versao.py` (ex.: `1.0.1`).
2. `powershell -ExecutionPolicy Bypass -File instalador\gerar_instalador.ps1` (precisa de Inno Setup 6). Roda os testes, empacota e gera
   `%TEMP%\zandao_tibia_tools_build\output\ZandaoTibiaToolsSetup.exe`.
3. Commit + push, e uma Release com a tag `v1.0.1` com o `ZandaoTibiaToolsSetup.exe` anexado.
   Quem já instalou recebe o aviso na próxima vez que abrir o programa.

