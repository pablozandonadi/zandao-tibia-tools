# Zandao Tibia Tools

Um programa só para quem joga Tibia, com cinco abas:

| Aba | O que faz |
| --- | --- |
| **Embuimentos** | Calculadora dos embuimentos Powerful (mesmas regras da planilha `calculadora_embuiment`). Você digita os preços, sem IA e sem ler prints. |
| **Hunt Analyser** | Loot Split + Tibia Damage juntos: cola os textos do Tibia e sai a análise no estilo do hunt-analyser.com. |
| **Histórico** | Toda hunt analisada fica salva neste PC. Dá para filtrar por personagem, exportar e importar. |
| **Prints** | Organiza as screenshots do Tibia em `Personagem / Tipo (/ Mês)`. |
| **Simulated Keys** | Segurar uma tecla repete outra no Tibia (segurar F → F1 etc.). Liga, desliga e mostra se está rodando. |

Os projetos antigos (`zandao embuimentos`, `tibia-screenshot-organizer-1.0.3`, `macro ek`, `divisor de loot`, `tibiadamage`) continuam
funcionando separados. Esta pasta tem as suas próprias cópias.

## Hunt Analyser

1. No Tibia, clique em **Copy** no **Party Hunt Analyser** e depois em **📋 Colar do Tibia**. Faça o mesmo com o
   **Hunting Analyser** (a sua hunt: XP, monstros e itens) e com o **Input Analyser** (Received Damage). O app
   reconhece qual texto é qual. Dá também para colar direto nas caixas, e o que cair na caixa errada vai para a certa.
2. Em **Seu personagem**, escolha quem é você: o Hunting Analyser fica ligado a esse membro da party.
3. A análise sai sozinha:
   - **Resumo da hunt**: duração, XP e Raw XP (e por hora), balance, lucro por membro, balance/h, top dano, despesas.
   - **Membros da party**: dano e cura (com %), loot, supplies, balance e quanto cada um recebe ou paga.
     Clique no nome para tirar alguém da divisão.
   - **Distribuição dos pagamentos**: os `transfer N to Fulano` com botão de copiar e a caixinha **Pago?**.
   - **Detalhes por membro** e **Monstros mortos** (com imagem).
   - **Dano recebido**: distribuição por elemento (o Damage Input é o dano real; sem ele, estima pelos ataques
     da TibiaWiki), **proteções recomendadas** (botão leva direto para a aba Embuimentos) e **melhor elemento
     para atacar** (pelas resistências da TibiaWiki), com a ficha de cada monstro.
4. **Despesas extras** (boat, hireling...): quem pagou é reembolsado na divisão. **Copiar resumo** gera o texto para o Discord.

As contas do Loot Split são as mesmas do `divisor de loot` (TibiaLootSplit). A parte de dano é o Tibia Damage
portado para Python, com duas correções: os embuimentos de proteção certos (Dragon Hide = fogo,
Cloud Fabric = energia, Quara Scale = gelo, Snake Skin = terra, Lich Shroud = morte, Demon Presence = sagrado) e o
Damage Input valendo sozinho quando existe (o site misturava com a estimativa da wiki).

As fichas dos monstros vêm da internet (TibiaWiki + TibiaData) só na primeira vez; ficam em `cache_monstros.json`.

## Histórico

Cada análise é salva automaticamente em `historico_hunts.json`, só neste computador, igual ao Zandonadi Radar:
cada pessoa tem o seu. Analisar a mesma hunt de novo atualiza a entrada (não duplica). Colar uma hunt de outro
horário cria uma entrada nova. Limpar uma caixa nunca apaga o que já está salvo.

- **Abrir** recarrega a hunt no Hunt Analyser (com as transferências já marcadas como pagas).
- **Exportar** gera um `.json` com todas as hunts (ou só as do personagem filtrado).
- **Importar (somar)** traz as hunts de um arquivo exportado, seu ou de um amigo, sem repetir as que você já tem.
  **Importar substituindo tudo** apaga o seu histórico e fica só com o do arquivo.

## Instalar

Baixe o **ZandaoTibiaToolsSetup.exe** na última Release do GitHub
(https://github.com/pablozandonadi/zandao-tibia-tools/releases/latest) e rode. Não precisa de administrador,
de Python nem de AutoHotkey. O programa fica em `%LOCALAPPDATA%\Programs\Zandao Tibia Tools`.

Cada pessoa começa do zero: o instalador não leva histórico, preços nem teclas de ninguém. Ao abrir, o programa
avisa quando sai versão nova e se atualiza sozinho; histórico, preços, pastas e teclas continuam salvos.

O Windows pode mostrar o aviso do SmartScreen ("O Windows protegeu o computador"), porque o instalador não
tem assinatura digital: clique em **Mais informações → Executar assim mesmo**. Alguns antivírus também
desconfiam do `SimulatedKeys.exe` (todo programa que simula teclado é suspeito para eles).

## Usar por cima do Tibia

No fim do menu lateral:

- **📌 Fixar por cima**: a janela fica na frente do Tibia, mesmo quando você clica no jogo.
- **Transparência**: deixa a janela de 40% a 100% opaca, para ver o jogo por trás.

Diminua a janela e coloque num canto: com menos de ~760 px de largura, o menu vira só ícones.
As duas opções ficam salvas em `preferencias.json`. Funciona com o Tibia em janela ou em tela cheia sem bordas.

## Embuimentos

1. Marque à esquerda os embuimentos que vai fazer (dá para filtrar por grupo).
2. Preencha o preço do Gold Token, a taxa de embuir e, no meio, o preço unitário de cada item e do scroll pronto.
   Aceita `4.475`, `4,475`, `4.5k` ou `1.2kk`. Em **Já tenho**, coloque o que já está no seu inventário.
3. O resultado à direita atualiza sozinho: **FAÇA ASSIM**, as 4 rotas (scroll pronto, itens no market,
   6 tokens, 4 tokens + último item) e a comparação do plano inteiro. Use **Copiar resultado** para colar no Discord.

Tudo o que você digita fica salvo em `dados_embuimentos.json`. Para adicionar ou alterar embuimentos, edite
`data/imbuements.json`. Só Void, Strike e Vampirism têm rota de token (`has_token: true`).

## Prints

As mesmas opções do Tibia Screenshot Organizer, salvas no `settings.json` desta pasta.

## Simulated Keys

É o macro EK (`macro/tibia_macro_f1.ahk`), compilado no instalador como `macro/SimulatedKeys.exe`: roda sem o
AutoHotkey instalado. As teclas de cada pessoa ficam em `macro/tibia_macro_config.ini` (criado no primeiro uso,
com F → F1). Rodando pelo código-fonte, sem o `.exe`, usa o AutoHotkey **v1.1** instalado.

- Alt+Shift+M liga e desliga.
- Alt+Shift+F10 abre a configuração das teclas.

O atalho "Iniciar com o Windows" se chama `ZandaoSimulatedKeys.lnk`.
Não deixe outro macro com as mesmas teclas rodando junto (ex.: o `macro ek` antigo).

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
build.bat                         # testes + gera um exe avulso nesta pasta (sem o Simulated Keys compilado)
```

### Lançar uma versão nova (atualização automática)

1. Aumente `VERSAO_APP` em `versao.py` (ex.: `1.0.1`).
2. `powershell -ExecutionPolicy Bypass -File instalador\gerar_instalador.ps1` (precisa de Inno Setup 6 e
   AutoHotkey v1.1 com o compilador). Roda os testes, empacota, compila o Simulated Keys e gera
   `%TEMP%\zandao_tibia_tools_build\output\ZandaoTibiaToolsSetup.exe`.
3. Commit + push, e uma Release com a tag `v1.0.1` com o `ZandaoTibiaToolsSetup.exe` anexado.
   Quem já instalou recebe o aviso na próxima vez que abrir o programa.

