# Histórico de preços dos Embuimentos + Ranking no comparativo + Prey + Party por hora

Data: 2026-10-07 · Versão alvo: 1.0.6 (não publicar sem "pode" explícito)

## Objetivo

1. **Preços:** guardar os preços que o usuário pesquisa no Market, com data, para ele saber se um item está mais caro ou mais barato que da última vez e ver a evolução em um gráfico.
2. **Comparativo:** ao comparar de 2 a 4 hunts lado a lado, mostrar quem é o 1º, o 2º... (o ranking somado que já existe em "Comparar todas") e deixar claro que as colunas "/h" são uma projeção para 1 hora, porque é isso que torna justa a comparação entre hunts de durações diferentes.
3. **Prey:** marcar em cada hunt se houve prey (tipo e estrelas), para entender as diferenças ao comparar hunts.
4. **Party por hora:** na tabela de membros da party, mostrar Dano/h, Cura/h e Profit/h.

Fora do escopo: preços automáticos (sem API do Market), sincronizar preços entre PCs e mudar a conta do "/h", que já está certa: `valor × 60 ÷ minutos`.

---

## Parte 1: Histórico de preços

### Dados

Arquivo novo **`precos_historico.json`** na mesma pasta do `dados_embuimentos.json` (`BASE_DIR`).

```json
{
  "item:rope belt": [{"data": "2026-10-03", "preco": 4600}, {"data": "2026-10-07", "preco": 4973}],
  "scroll:void":    [{"data": "2026-10-07", "preco": 590090}],
  "token":          [{"data": "2026-10-07", "preco": 55554}],
  "blank":          [{"data": "2026-10-07", "preco": 25000}]
}
```

- As chaves são as mesmas que a tela já usa (`emb.item_key`, `emb.scroll_key`), mais `token` e `blank`. A taxa de embuir é um valor fixo de NPC e não entra.
- Cada lista fica em ordem de data crescente, com **no máximo 1 registro por dia**.
- O arquivo fica separado do `dados_embuimentos.json` porque aquele é reescrito a cada tecla digitada. O histórico só cresce e não pode correr esse risco.
- A gravação é atômica, como no `historico.py`: grava um `.tmp` e depois troca pelo arquivo final.
- Entra no `.gitignore` (`precos_historico.json` e `precos_historico.json.tmp`).
- Entra no Backup com a chave `"precos"` e o rótulo "Histórico de preços dos embuimentos" (`backup.ITENS` e `_caminhos_backup()` no `web_api.py`).

### Módulo `precos.py` (sem interface, testável)

| Função | O que faz |
|---|---|
| `carregar(caminho=None) -> dict` | Lê o arquivo. Se ele não existir ou estiver corrompido, devolve `{}` sem dar erro. |
| `registrar(precos: dict[str, int\|None], data: str, caminho=None) -> int` | Para cada chave com preço > 0, grava `{data, preco}`. Se já houver registro nessa data, substitui o valor. Devolve quantos preços gravou. Ignora `None` e 0. |
| `ultimo_antes(historico, chave, data) -> dict\|None` | Devolve o último registro com data **anterior** a `data`. É a base de comparação do aviso. |
| `variacao(preco_atual, chave, hoje, historico) -> dict\|None` | Devolve `{"pct": 8.1, "antes": 4600, "data": "2026-10-03", "sentido": "subiu"\|"caiu"}`. Devolve `None` se não houver registro anterior, se o preço atual estiver vazio ou se for igual ao anterior. |
| `serie(historico, chave) -> dict` | Devolve `{"pontos": [...], "min", "max", "media"}` para o gráfico. |
| `apagar(chave, data, caminho=None) -> bool` | Remove um registro (para corrigir um preço errado). |

A data vem de fora (`date.today().isoformat()` no `web_api`), o que deixa os testes determinísticos.

### API (`web_api.py`)

- `precos_registrar(precos_texto: dict) -> {"gravados": n}`: recebe os textos digitados (itens, scrolls, token, blank), converte com `emb.parse_num` e chama `precos.registrar` com a data de hoje.
- `precos_variacoes(precos_texto: dict) -> {chave: variacao|None}`: devolve o aviso de cada campo preenchido.
- `precos_serie(chave) -> serie` e `precos_apagar(chave, data) -> serie atualizada`.

### Tela (aba Embuimentos)

- **Botão "📌 Registrar preços de hoje"** logo acima da lista de itens. Ele chama `precos_registrar` e mostra o toast "12 preços registrados". Se não houver nenhum preço preenchido, o toast diz "Nenhum preço preenchido".
  - Nada vai para o histórico sem esse clique. Foi uma decisão do usuário.
- **Aviso por campo** (itens, scroll pronto, gold token, blank scroll): uma linha pequena embaixo do input.
  - `▲ 8% · antes 4.600 (03/10)` em vermelho, quando está mais caro.
  - `▼ 5% · antes 5.230 (03/10)` em verde, quando está mais barato.
  - Fica vazio quando não há registro anterior ou o preço é igual.
  - Atualiza junto com o cálculo, no mesmo debounce de 180 ms (uma chamada a `precos_variacoes`).
  - Compara com o último registro **anterior a hoje**. Assim, depois de registrar hoje, o aviso continua mostrando a mudança em relação à pesquisa anterior.
- **Gráfico:** o nome do item (e "Scroll pronto", "Gold token", "Blank scroll") vira clicável e abre um painel/modal com:
  - um gráfico de linha em SVG desenhado à mão, no mesmo estilo do gráfico de "Comparar todas", sem biblioteca, para funcionar offline;
  - menor, maior e média;
  - a lista de data e preço (mais recente primeiro), com ✕ para apagar um registro;
  - com só 1 registro, o painel mostra o ponto e o texto "Registre mais dias para ver a evolução".
  - O 📋 (copiar nome) continua funcionando separado do clique no nome.

### Erros

- Se a gravação falhar (OSError), o toast mostra "Não consegui salvar o histórico de preços" e o arquivo antigo fica intacto.
- Uma chave do histórico que não existe mais na tela é ignorada sem erro.

### Testes (`test_precos.py`)

- `registrar` grava, substitui no mesmo dia, ignora None/0 e mantém a ordem por data.
- `variacao` cobre: subiu, caiu, igual (`None`), sem histórico (`None`) e registro de hoje ignorado na comparação.
- `serie` calcula min, max e média; `apagar` remove só o registro certo.
- Arquivo corrompido vira `{}` em `carregar`.
- O backup exporta e importa a chave `precos`.

---

## Parte 2: Ranking no comparativo lado a lado

### Backend (`historico.py`)

- Extrair de `panorama()` a função **`ranking_jogadores(hunts) -> list`**. Ela soma dano, cura, supplies, loot, balance e minutos por jogador, considerando só as hunts em que ele estava, e calcula `dano_h`, `cura_h`, `supplies_h` e `balance_media`, ordenando por `dano_h` decrescente.
- `panorama()` passa a usar essa função, e o resultado não muda.
- `comparar()` ganha o campo **`ranking`**, gerado pela mesma função.
- `cab` (o cabeçalho de cada hunt) já tem `duracao` e passa a ser exibido na tela.

### Tela (`index.html`)

- Extrair o HTML da tabela "Ranking por jogador" do panorama para a função **`htmlRanking(jogadores)`**, com ordenação ao clicar na coluna.
  - O panorama e o comparativo passam a usar essa mesma função.
- No comparativo, a ordem fica assim:
  1. avisos e veredito (como hoje);
  2. **👥 Ranking por jogador (somando estas hunts)** com `htmlRanking(r.ranking)`;
  3. a nota: *"/h = projeção para 1 hora: uma hunt de 1h17 é dividida por 1,28 (puxa para baixo), uma de 40 min é multiplicada por 1,5 (puxa para cima). Cada jogador conta só o tempo das hunts em que estava."*;
  4. **Detalhe por hunt:** a tabela atual "Por jogador", com uma coluna por hunt e a ⭐, que agora abre em **"Dano / hora"**. Cada cabeçalho mostra `PT 4 · 1h17`.

### Testes (`test_hunt.py`)

- `comparar([A, B])["ranking"]` é igual a `panorama([A, B])["jogadores"]`.
- Um jogador que estava só em uma das hunts tem `hunts == 1` e `minutos` igual à duração só daquela hunt.
- Os testes de `panorama` que já existem continuam passando, o que garante que a extração não mudou nenhum número.

---

## Parte 3: Marcar a prey da hunt

O app **não calcula nada** de prey: os números colados do Hunt Analyser do Tibia já vêm com o efeito dela. O objetivo é só registrar qual prey estava ativa, para explicar as diferenças quando duas hunts forem comparadas. A marcação vale **só para o personagem do usuário**, não para os outros membros da party.

### Dados

A hunt salva em `historico_hunts.json` ganha o campo opcional `prey`:

```json
"prey": [{"tipo": "xp", "estrelas": 7}, {"tipo": "loot", "estrelas": 4}]
```

- `tipo` ∈ `xp`, `loot`, `ataque`, `defesa`; `estrelas` é um inteiro de 1 a 10. São no máximo 3 itens, que é o número de slots do Tibia.
- `[]` = **sem prey**. Sem o campo = **prey não informada** (todas as hunts antigas). Os dois casos são diferentes e nunca devem ser confundidos.
- `historico.py` ganha `normalizar_prey(valor) -> list|None`, que valida o tipo e limita as estrelas entre 1 e 10, descartando entradas inválidas. Ela é usada em `salvar()`, em `atualizar()` e na importação.
- Rótulos: `xp` → "XP", `loot` → "Loot", `ataque` → "Ataque", `defesa` → "Defesa". Formato do texto: `Prey XP ★7`. Várias preys ficam separadas por " + ". Lista vazia → "Sem prey". `None` → "Prey não informada".

### Tela

- **Hunt Analyser:** uma linha "Prey" perto do botão Salvar, com 3 slots. Cada slot tem um select de tipo (Nenhuma, XP, Loot, Ataque, Defesa) e um select de estrelas (★1 a ★10), que só aparece quando o tipo não é "Nenhuma".
  - O valor inicial é a prey da última hunt salva desse personagem. Se não houver nenhuma, todos os slots começam em "Nenhuma".
  - Salvar com todos os slots em "Nenhuma" grava `[]`, ou seja, sem prey.
- **Histórico:** cada hunt mostra um chip com o texto da prey. Hunts com "Prey não informada" mostram o chip apagado. Ao abrir uma hunt salva, dá para editar a prey e clicar em Salvar (o `salvar()` preserva a prey quando a entrada não traz o campo).
- **Comparativo:** o cabeçalho de cada hunt mostra `PT 4 · 1h17 · Prey XP ★7`.

### Aviso no `comparar()`

Ele só aparece se **todas** as hunts comparadas tiverem a prey informada e as preys forem diferentes. Para isso, compara o conjunto de pares `(tipo, estrelas)` de cada hunt:

> "Prey diferente: 'Hunt A' com Prey XP ★7, 'Hunt B' sem prey. A XP/h (prey de XP), o loot (prey de Loot) e o dano (prey de Ataque/Defesa) não são comparáveis diretamente."

O texto final cita só os tipos envolvidos.

### Testes (`test_hunt.py`)

- `normalizar_prey`: tipo inválido é descartado, estrelas 0 ou 11 ficam limitadas a 1 ou 10, mais de 3 itens é cortado e `None` continua `None`.
- `salvar` e `atualizar` gravam a prey, e uma hunt antiga sem o campo continua sem ele.
- O aviso aparece com preys diferentes, não aparece com preys iguais e não aparece quando alguma hunt tem a prey não informada.
- Exportar e importar o histórico mantém o campo `prey`.

---

## Parte 4: Valores por hora na tabela da party (Hunt Analyser)

Só na análise de **party** do Hunt Analyser. O comparativo não muda. A análise solo já mostra Dano/h e Cura/h.

### Backend (`hunt.py`, em `montar()`)

- Cada item de `membros` ganha:
  - `dano_h = _por_hora(p.damage, minutos)`;
  - `cura_h = _por_hora(p.healing, minutos)`;
  - `balance_h = _por_hora(p.balance, minutos)`, que na tela aparece como "Profit/h" e é o lucro ou gasto de cada um **antes** da divisão.
- O `resumo` da party ganha `lucro_h = _por_hora(split.fair_share_per_player, minutos)`, o lucro final por membro por hora.
- Sem duração (`minutos` vazio ou 0), todos esses campos ficam `None`.

### Tela (`index.html`)

- Tabela de membros: `# · Membro · Dano · Dano/h · Cura · Cura/h · Loot · Supplies · Balance · Profit/h · Ajuste`. As colunas /h usam um tom mais apagado (classe `dim`), e um valor `None` aparece como "—". O Profit/h usa as mesmas cores de positivo e negativo do Balance.
- Resumo da party: um stat novo, **"Lucro/h (por membro)"**, ao lado de "Lucro final (por membro)".
- O card de cada membro (o detalhe com Paga/Recebe) ganha Dano/h e Cura/h.

### Testes (`test_hunt.py`)

- Na hunt real do teste de party que já existe, `dano_h`, `cura_h` e `balance_h` de cada membro são iguais a `valor × 60 // minutos`, e `resumo["lucro_h"]` é igual a `lucro × 60 // minutos`.
- Sem duração, todos esses campos são `None`.

---

## Verificação

- `python -m pytest` (ou os testes no formato atual do projeto) passa por completo.
- A UI é testada no painel do navegador com o servidor de teste que simula `window.pywebview.api`:
  - registrar preços, mudar um valor e ver ▲/▼, abrir o gráfico e apagar um registro;
  - comparar 2 hunts e conferir que o ranking bate com o do "Comparar todas".
- A versão sobe para 1.0.6 no `versao.py`. Gerar o instalador e publicar só com autorização explícita.
