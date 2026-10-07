# Preços, Comparativo, Prey e Party por hora: Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** histórico de preços dos embuimentos com aviso ▲/▼ e gráfico; ranking somado no comparativo lado a lado; marcação de prey nas hunts; Dano/h, Cura/h e Profit/h na tabela da party.

**Architecture:** a lógica fica em módulos Python puros e testáveis (`precos.py` novo, `historico.py`, `hunt.py`), expostos ao `web/index.html` por métodos da classe da API em `web_api.py` (pywebview, `window.pywebview.api`). A tela só formata: nenhum cálculo de negócio no JS.

**Tech Stack:** Python 3 + `unittest` (rodar com `python -m unittest`), pywebview, HTML/JS puro com gráficos em SVG desenhados à mão (sem bibliotecas).

**Spec:** `docs/superpowers/specs/2026-10-07-precos-e-comparativo-design.md`

## Global Constraints

- Versão alvo **1.0.6** (`versao.py`). **Não publicar** (push/Release) nem instalar no PC sem "pode" explícito do usuário.
- Dados pessoais nunca vão para o GitHub: todo arquivo de dados novo entra no `.gitignore`.
- Toda gravação de JSON é atômica: grava `.tmp` e depois `os.replace`, como em `historico._gravar`.
- Valores "por hora" sempre com `valor * 60 // minutos`. Sem minutos, o resultado é `None` e a tela mostra "—".
- Listas e rankings por jogador sempre "maior primeiro".
- Textos da tela em português, no tom das telas atuais. Números com `n()` / `ouro()` do `index.html`.
- Commits com o e-mail noreply do GitHub, que já está configurado no repo, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Abrir uma hunt antiga (sem prey) e clicar em "Salvar alterações"** não pode gravar uma prey que o usuário não escolheu. A prey continua "não informada". O padrão "prey da última hunt" vale só para hunt **nova**. (Testes nas Tasks 7 e 8.)
2. **Preço digitado como `4.5k`, `1.2kk` ou `4,475`** precisa ser registrado com o mesmo número que o cálculo usa (`emb.parse_num`). (Teste na Task 2.)
3. **Campo de preço apagado ao registrar** é ignorado: não apaga o histórico daquele item nem grava 0. (Teste na Task 1.)
4. **Hunt sem duração** (texto sem "Session:"): as colunas /h mostram "—" sem quebrar a tabela. (Teste na Task 5.)
5. **Mesmo item usado em dois embuimentos** (mesma chave `item:...`) gera um único registro por dia, e o aviso aparece igual nos dois cards. (Teste na Task 1; na tela, Task 3, Step 2.)

---

### Task 1: Módulo `precos.py` (histórico de preços)

**Files:**
- Create: `precos.py`
- Test: `test_precos.py`
- Modify: `.gitignore` (acrescentar `precos_historico.json` e `precos_historico.json.tmp` no bloco de dados pessoais)

**Interfaces:**
- Produces:
  - `PRECOS_PATH: str`: `os.path.join(BASE_DIR, "precos_historico.json")`, com `BASE_DIR` resolvido como em `historico.py` (pasta do exe quando frozen, senão a pasta do arquivo).
  - `carregar(caminho=None) -> dict[str, list[dict]]`
  - `registrar(precos: dict[str, int | None], data: str, caminho=None) -> int`
  - `ultimo_antes(historico: dict, chave: str, data: str) -> dict | None`
  - `variacao(preco_atual: int | None, chave: str, hoje: str, historico: dict) -> dict | None` → `{"pct": float, "antes": int, "data": "AAAA-MM-DD", "sentido": "subiu" | "caiu"}`
  - `serie(historico: dict, chave: str) -> {"pontos": [{"data", "preco"}], "min": int|None, "max": int|None, "media": int|None}`
  - `apagar(chave: str, data: str, caminho=None) -> bool`

- [ ] **Step 1: Escrever os testes que falham** em `test_precos.py` (classe `TestPrecos`, `tempfile.TemporaryDirectory` no `setUp`, como em `TestHistorico`):

```python
def test_registrar_substitui_no_mesmo_dia_e_ignora_vazios(self):
    self.assertEqual(precos.registrar({"item:rope belt": 4600, "token": None, "blank": 0}, "2026-10-03", self.arq), 1)
    precos.registrar({"item:rope belt": 4700}, "2026-10-03", self.arq)
    precos.registrar({"item:rope belt": 4973}, "2026-10-07", self.arq)
    h = precos.carregar(self.arq)
    self.assertEqual(h["item:rope belt"], [{"data": "2026-10-03", "preco": 4700}, {"data": "2026-10-07", "preco": 4973}])
    self.assertNotIn("token", h)

def test_registro_fora_de_ordem_fica_ordenado(self):
    precos.registrar({"blank": 25000}, "2026-10-07", self.arq)
    precos.registrar({"blank": 24000}, "2026-10-01", self.arq)
    self.assertEqual([p["data"] for p in precos.carregar(self.arq)["blank"]], ["2026-10-01", "2026-10-07"])

def test_campo_vazio_nao_apaga_historico(self):
    precos.registrar({"item:rope belt": 4600}, "2026-10-03", self.arq)
    precos.registrar({"item:rope belt": None}, "2026-10-07", self.arq)
    self.assertEqual(len(precos.carregar(self.arq)["item:rope belt"]), 1)

def test_variacao(self):
    h = {"item:rope belt": [{"data": "2026-10-03", "preco": 4600}, {"data": "2026-10-07", "preco": 4973}]}
    v = precos.variacao(4973, "item:rope belt", "2026-10-07", h)   # registro de hoje é ignorado
    self.assertEqual((v["sentido"], v["antes"], v["data"]), ("subiu", 4600, "2026-10-03"))
    self.assertAlmostEqual(v["pct"], 8.1, places=1)
    self.assertEqual(precos.variacao(4370, "item:rope belt", "2026-10-07", h)["sentido"], "caiu")
    self.assertIsNone(precos.variacao(4600, "item:rope belt", "2026-10-07", h))   # igual
    self.assertIsNone(precos.variacao(None, "item:rope belt", "2026-10-07", h))   # vazio
    self.assertIsNone(precos.variacao(5000, "item:outro", "2026-10-07", h))       # sem histórico

def test_serie_e_apagar(self):
    for d, p in (("2026-10-01", 100), ("2026-10-02", 300), ("2026-10-03", 200)):
        precos.registrar({"token": p}, d, self.arq)
    s = precos.serie(precos.carregar(self.arq), "token")
    self.assertEqual((s["min"], s["max"], s["media"]), (100, 300, 200))
    self.assertTrue(precos.apagar("token", "2026-10-02", self.arq))
    self.assertFalse(precos.apagar("token", "2026-10-02", self.arq))
    self.assertEqual([p["preco"] for p in precos.carregar(self.arq)["token"]], [100, 200])
    self.assertEqual(precos.serie({}, "token"), {"pontos": [], "min": None, "max": None, "media": None})

def test_arquivo_corrompido(self):
    open(self.arq, "w").write("{quebrado")
    self.assertEqual(precos.carregar(self.arq), {})
```

- [ ] **Step 2: Rodar e ver falhar**
  - Comando: `python -m unittest test_precos -v`
  - Esperado: `ModuleNotFoundError: No module named 'precos'`

- [ ] **Step 3: Implementar `precos.py`** com as assinaturas acima.
  - Usar `threading.Lock` em `registrar` e `apagar`, como `historico._trava`.
  - `media` é a média inteira (`//`).
  - `pct` = `round((atual - antes) / antes * 100, 1)`.
  - `carregar` descarta chaves cujo valor não seja lista.

- [ ] **Step 4: Rodar e ver passar**
  - Comando: `python -m unittest test_precos -v`
  - Esperado: 6 testes OK.

- [ ] **Step 5: Commit** com `precos.py`, `test_precos.py` e `.gitignore`. Mensagem: `Precos: historico de precos dos embuimentos (modulo + testes)`.

---

### Task 2: API de preços + Backup

**Files:**
- Modify: `web_api.py` (métodos novos na seção `# ===== embuimentos =====`, depois de `calcular`; `_caminhos_backup()` na linha ~803)
- Modify: `backup.py` (`ITENS`: `"precos": "Histórico de preços dos embuimentos"`)
- Test: `test_precos.py` (classe `TestApiPrecos`) e o teste de backup existente em `test_hunt.py` (~linha 398)

**Interfaces:**
- Consumes: Task 1 (`precos.*`), `emb.parse_num(str) -> int | None`
- Produces (métodos da classe da API, chamados no JS por `api.<nome>`):
  - `precos_registrar(precos_texto: dict[str, str]) -> {"gravados": int}`, ou `{"erro": "Não consegui salvar o histórico de preços"}` em caso de OSError
  - `precos_variacoes(precos_texto: dict[str, str]) -> dict[str, dict | None]`
  - `precos_serie(chave: str) -> serie`
  - `precos_apagar(chave: str, data: str) -> serie` (a série já atualizada)
  - Em todos, a data de hoje vem de `date.today().isoformat()`, por meio de `self._hoje()` para os testes poderem trocar. O caminho vem de `precos.PRECOS_PATH`, por meio de `self._precos_path` para os testes poderem trocar.

- [ ] **Step 1: Escrever os testes que falham.** Instanciar a classe da API com `object.__new__(<classe da API>)` e setar só `_precos_path` (um arquivo temporário) e `_hoje`.

```python
def test_registrar_aceita_formatos_do_tibia(self):
    api._hoje = lambda: "2026-10-07"
    self.assertEqual(api.precos_registrar({"item:rope belt": "4.5k", "scroll:void": "1,2kk", "token": "55554", "blank": ""}),
                     {"gravados": 3})
    h = precos.carregar(api._precos_path)
    self.assertEqual(h["item:rope belt"][0]["preco"], emb.parse_num("4.5k"))
    self.assertEqual(h["scroll:void"][0]["preco"], emb.parse_num("1,2kk"))

def test_variacoes(self):
    api._hoje = lambda: "2026-10-03"; api.precos_registrar({"token": "50000"})
    api._hoje = lambda: "2026-10-07"
    v = api.precos_variacoes({"token": "55000", "blank": "25000"})
    self.assertEqual(v["token"]["sentido"], "subiu")
    self.assertIsNone(v["blank"])
```

  No teste de backup existente, acrescentar um arquivo `precos` em `orig` e conferir que ele volta igual depois de `backup.importar`.

- [ ] **Step 2: Rodar e ver falhar**
  - Comando: `python -m unittest test_precos test_hunt -v`
  - Esperado: `AttributeError: ... 'precos_registrar'` e uma falha no backup.

- [ ] **Step 3: Implementar.**
  - Os 4 métodos no `web_api.py`.
  - `"precos": precos.PRECOS_PATH` em `_caminhos_backup()`.
  - O rótulo em `backup.ITENS`.
  - `_precos_path` e `_hoje` são atributos de classe com valor padrão, para não precisar mexer no `__init__`.

- [ ] **Step 4: Rodar tudo**
  - Comando: `python -m unittest`
  - Esperado: todos OK (os testes antigos e os novos).

- [ ] **Step 5: Commit** `Precos: API (registrar, variacoes, serie, apagar) e backup`.

---

### Task 3: Tela de preços (aba Embuimentos)

**Files:**
- Modify: `web/index.html`
  - CSS no `<style>`;
  - `montarItens()` (~linha 780);
  - card de gold token/blank (ids `v-token`, `v-blank`);
  - `calcular()` (~linha 830);
  - modal novo.

**Interfaces:**
- Consumes: Task 2 (`api.precos_registrar`, `api.precos_variacoes`, `api.precos_serie`, `api.precos_apagar`); a função de gráfico SVG do panorama (`graficoEvolucao`, ~linha 1580) como referência de estilo.
- Produces:
  - `precosTexto() -> {chave: texto}`: junta `estado.precos` com `token: estado.token` e `blank: estado.blank`.
  - `abrirGraficoPreco(chave, nome)`.

- [ ] **Step 1: Botão "📌 Registrar preços de hoje"** acima de `#itens`.
  - Ao clicar, chama `api.precos_registrar(precosTexto())`.
  - Se `gravados > 0`, mostra o toast `"${gravados} preços registrados"`.
  - Se `gravados == 0`, mostra o toast `"Nenhum preço preenchido"` com erro.
  - Se vier `erro`, mostra um toast de erro.
  - Depois, atualiza os avisos.

- [ ] **Step 2: Aviso por campo.**
  - Embaixo de cada input de preço (itens, scroll, token, blank) entra um `<div class="var-preco" data-var="CHAVE"></div>`.
  - Dentro do mesmo `setTimeout` de 180 ms do `calcular()`, chamar `api.precos_variacoes(precosTexto())` e preencher:
    - **subiu:** classe `neg` e o texto `▲ ${pct}% · antes ${n(antes)} (${dd/mm})`;
    - **caiu:** classe `pos` e o texto `▼ ...`;
    - **null:** vazio.
  - Atualizar **todos** os `[data-var="CHAVE"]`, porque o mesmo item pode aparecer em dois cards.

- [ ] **Step 3: Gráfico.**
  - O nome do item, "Scroll pronto", "Gold token" e "Blank scroll" ganham `data-grafico-preco="CHAVE"` e cursor pointer. O botão 📋 continua com o próprio handler e chama `stopPropagation`.
  - O clique abre um modal com:
    - um SVG de linha (eixo X = datas, eixo Y = preço, média tracejada, título no hover com data e preço);
    - os chips `menor`, `maior` e `média`;
    - a lista mais recente primeiro, cada uma com o botão ✕, que chama `api.precos_apagar` e redesenha.
  - Com 1 ponto, mostrar o texto "Registre mais dias para ver a evolução".
  - Com 0 pontos, mostrar "Nenhum preço registrado ainda. Use 📌 Registrar preços de hoje."
  - Fecha no ✕, no Esc e no clique fora do modal.

- [ ] **Step 4: Verificar na tela.** Usar o servidor de teste que simula `window.pywebview.api`. Uma cópia está em `C:\Users\Zandao\AppData\Local\Temp\claude\G--Meu-Drive-CLAUDE-CODE\0d749a5f-3dea-4bf5-9383-912bd307bb29\scratchpad\servidor_teste.py`; copie para o scratchpad da sessão e acrescente os métodos novos.
  - Roteiro:
    1. registrar;
    2. mudar o Rope Belt para um valor maior e ver ▲ em vermelho;
    3. abrir o gráfico;
    4. apagar um ponto;
    5. ver que o console não tem erros.
  - Tirar um screenshot como prova.

- [ ] **Step 5: Commit** `Embuimentos: botao registrar precos, aviso de variacao e grafico por item`.

---

### Task 4: `ranking_jogadores` compartilhado + `ranking` no comparar

**Files:**
- Modify: `historico.py`: extrair de `panorama()` o bloco que monta `jogadores` e `ranking`; acrescentar `ranking` em `comparar()`.
- Test: `test_hunt.py` (classe `TestComparar`)

**Interfaces:**
- Produces:
  - `ranking_jogadores(hunts: list[dict]) -> list[dict]`. Cada item tem `{"nome", "hunts", "minutos", "dano", "cura", "supplies", "loot", "balance", "dano_h", "cura_h", "supplies_h", "balance_media"}` e a lista vem ordenada por `dano_h` decrescente.
  - `comparar(hunts)["ranking"]`.
  - `panorama(hunts)["jogadores"]` continua com o mesmo conteúdo de hoje.

- [ ] **Step 1: Escrever os testes que falham** em `TestComparar`. Para hunts com membros, mover o helper `_reg` de `TestPanorama` para uma função de módulo `_reg_party(id_, inicio, duracao, k, mons)` usada pelas duas classes.

```python
def test_ranking_igual_ao_panorama(self):
    a = _reg_party("a", "2026-10-01, 10:00:00", "01:17h", 1, ["gloom maws"])
    b = _reg_party("b", "2026-10-02, 10:00:00", "02:00h", 2, ["gloom maws"])
    self.assertEqual(historico.comparar([a, b])["ranking"], historico.panorama([a, b])["jogadores"])

def test_ranking_usa_so_o_tempo_de_quem_estava(self):
    a = _reg_party("a", "2026-10-01, 10:00:00", "01:00h", 1, ["varg"])
    b = _reg_party("b", "2026-10-02, 10:00:00", "02:00h", 1, ["varg"])
    b["entrada"]["party"] = b["entrada"]["party"].replace("Knight Alfa", "Knight Zulu")
    r = {j["nome"]: j for j in historico.comparar([a, b])["ranking"]}
    self.assertEqual((r["Knight Alfa"]["hunts"], r["Knight Alfa"]["minutos"]), (1, 60))
    self.assertEqual(r["Knight Alfa"]["dano_h"], 12_846_796)
```

  Antes, confira em `historico._membros_da_hunt` (~linha 212) de onde vêm os membros. Se não for de `entrada.party`, troque o nome nesse campo no segundo teste.

- [ ] **Step 2: Rodar e ver falhar**
  - Comando: `python -m unittest test_hunt.TestComparar -v`
  - Esperado: `KeyError: 'ranking'`.

- [ ] **Step 3: Implementar.**
  - `ranking_jogadores` recebe as hunts e calcula `metricas()` + `_metricas_jogadores()` internamente.
  - `panorama()` passa a chamar `ranking_jogadores(hunts)`.
  - `comparar()` acrescenta `"ranking": ranking_jogadores(hunts)` no dict de retorno.

- [ ] **Step 4: Rodar tudo**
  - Comando: `python -m unittest`
  - Esperado: todos OK. Em especial, `TestPanorama.test_muitas_hunts` continua passando sem mudanças.

- [ ] **Step 5: Commit** `Historico: ranking_jogadores compartilhado; comparar devolve ranking`.

---

### Task 5: `/h` por membro na party (`hunt.py`)

**Files:**
- Modify: `hunt.py`, `montar()`, no laço de `membros` (~linha 120) e no `resumo.update` (~linha 132)
- Test: `test_hunt.py` (`TestParty`)

**Interfaces:**
- Produces: cada item de `a["membros"]` ganha `dano_h`, `cura_h` e `balance_h` (int | None). `a["resumo"]["lucro_h"]` (int | None) na party.

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_por_hora_dos_membros(self):
    a = hunt.montar({"party": PARTY})
    knight = next(m for m in a["membros"] if m["nome"] == "Knight Alfa")
    self.assertEqual(knight["dano_h"], 12_846_796 * 60 // 167)    # Session 02:47h = 167 min
    self.assertEqual(knight["cura_h"], 3_120_299 * 60 // 167)
    self.assertEqual(knight["balance_h"], -866_581 * 60 // 167)
    self.assertEqual(a["resumo"]["lucro_h"], 1_400_580 * 60 // 167)

def test_por_hora_sem_duracao(self):
    a = hunt.montar({"party": PARTY.replace("Session: 02:47h", "Session: 00:00h")})
    self.assertTrue(all(m["dano_h"] is None and m["balance_h"] is None for m in a["membros"]))
    self.assertIsNone(a["resumo"]["lucro_h"])
```

  `_por_hora` usa `//`. Para negativos, o teste usa a mesma conta, então os dois arredondam igual.

- [ ] **Step 2: Rodar e ver falhar**
  - Comando: `python -m unittest test_hunt.TestParty -v`
  - Esperado: `KeyError: 'dano_h'`.

- [ ] **Step 3: Implementar** com `_por_hora(p.damage, minutos)`, `_por_hora(p.healing, minutos)`, `_por_hora(p.balance, minutos)` e `"lucro_h": _por_hora(split.fair_share_per_player, minutos)`.

- [ ] **Step 4: Rodar tudo**
  - Comando: `python -m unittest`
  - Esperado: todos OK.

- [ ] **Step 5: Commit** `Hunt Analyser: dano/h, cura/h e profit/h por membro; lucro/h por membro`.

---

### Task 6: Tela do comparativo e da tabela da party

**Files:**
- Modify: `web/index.html`:
  - `renderPanorama` (~linha 1551);
  - `renderComparacao` e `renderJogadores` (~linhas 1653-1700);
  - `renderMembros` (~linha 1245);
  - o resumo do Hunt Analyser (~linha 1228);
  - o card de detalhe do membro (~linha 1278).

**Interfaces:**
- Consumes: Task 4 (`r.ranking`) e Task 5 (`m.dano_h`, `m.cura_h`, `m.balance_h`, `r.lucro_h`). No card de detalhe, pegue os /h em `a.membros` pelo nome se `detalhes` não os tiver.
- Produces: `htmlRanking(jogadores, col, attr)`, que devolve o HTML da tabela de ranking (cabeçalhos clicáveis com `data-${attr}`) e é usado pelo panorama (`attr = 'rk'`, variável `rankCol`) e pelo comparativo (`attr = 'rkc'`, com a variável própria `rankColComp = 'dano_h'`).

- [ ] **Step 1: Extrair `htmlRanking`** do trecho `jog` de `renderPanorama`, sem mudar a aparência do panorama.

- [ ] **Step 2: Comparativo.** Em `renderComparacao`, depois de avisos e veredito e antes da tabela de linhas, entram:
  - `<h2>👥 Ranking por jogador (somando estas hunts)</h2>` + `htmlRanking(r.ranking, rankColComp, 'rkc')`;
  - a nota com o texto exato da spec (Parte 2, item 3).

  Também:
  - A seção "Por jogador" atual passa a se chamar "Detalhe por hunt".
  - `compMetrica` começa em `'dano_h'`.
  - Os cabeçalhos de hunt (em `renderComparacao` e `renderJogadores`) mostram `PT 4 · 1h17`, usando `h.duracao`.

- [ ] **Step 3: Tabela da party.**
  - Colunas `Dano · Dano/h · Cura · Cura/h · Loot · Supplies · Balance · Profit/h · Ajuste`.
  - Dano/h e Cura/h em `<td class="r dim">`, com "—" quando o valor é null.
  - Profit/h com `ouro(m.balance_h)` (as mesmas cores do Balance; "—" se null).
  - No resumo, `stat('Lucro/h (por membro)', ouro(r.lucro_h))` logo depois de "Lucro final (por membro)", só quando `a.tem.party`.
  - No card de detalhe, `stat('Dano/h', ...)` e `stat('Cura/h', ...)`.

- [ ] **Step 4: Verificar na tela** com o servidor de teste:
  1. comparar 2 hunts e conferir o ranking (os mesmos números de "Comparar todas" filtrado nessas 2);
  2. ordenar o ranking por Cura/h clicando na coluna;
  3. ver a tabela da party com as colunas novas;
  4. ver que o console não tem erros.

  Tirar um screenshot.

- [ ] **Step 5: Commit** `Comparativo com ranking somado e nota de projecao; party com valores por hora`.

---

### Task 7: Prey no histórico (`historico.py`)

**Files:**
- Modify: `historico.py`: funções novas, `salvar` (bloco `preservar`), `importar` (normalizar `h["prey"]`) e `comparar` (`cab[*]["prey"]` + aviso)
- Test: `test_hunt.py` (classe nova `TestPrey`)

**Interfaces:**
- Produces:
  - `TIPOS_PREY = {"xp": "XP", "loot": "Loot", "ataque": "Ataque", "defesa": "Defesa"}`
  - `normalizar_prey(valor) -> list[dict] | None`: devolve `None` se `valor is None`; senão, no máximo 3 itens válidos `{"tipo", "estrelas"}` com o tipo em `TIPOS_PREY` e as estrelas convertidas para int, limitadas entre 1 e 10. Itens inválidos são descartados **antes** do corte em 3.
  - `rotulo_prey(prey: list | None) -> str`: `None` → `"Prey não informada"`, `[]` → `"Sem prey"`, senão `"Prey XP ★7 + Prey Loot ★4"`.
  - `comparar(...)["hunts"][i]["prey"]`, com o rótulo pronto (str).
  - Aviso: `'Prey diferente: "A" com Prey XP ★7, "B" sem prey. ' + final`. O `final` junta, na ordem XP → Loot → Ataque/Defesa, só os tipos presentes em alguma das hunts: `"A XP/h"`, `"o loot"`, `"o dano"`. Com um tipo: `"A XP/h não é comparável diretamente."`. Com vários: `"A XP/h e o loot não são comparáveis diretamente."`. Hunt sem prey aparece como `"B" sem prey`; com prey, como `"A" com <rótulo>`.

- [ ] **Step 1: Escrever os testes que falham.** Mover o `_reg` de `TestHistorico` e o `_h` de `TestComparar` para funções de módulo (`_reg_hist`, `_h_comp`), para reaproveitar nos testes de prey.

```python
def test_normalizar(self):
    self.assertIsNone(historico.normalizar_prey(None))
    self.assertEqual(historico.normalizar_prey([{"tipo": "xp", "estrelas": 11}, {"tipo": "x", "estrelas": 3},
                                                {"tipo": "loot", "estrelas": 0}, {"tipo": "ataque", "estrelas": "5"},
                                                {"tipo": "defesa", "estrelas": 2}]),
                     [{"tipo": "xp", "estrelas": 10}, {"tipo": "loot", "estrelas": 1}, {"tipo": "ataque", "estrelas": 5}])
    self.assertEqual(historico.rotulo_prey([{"tipo": "xp", "estrelas": 7}]), "Prey XP ★7")
    self.assertEqual(historico.rotulo_prey([]), "Sem prey")
    self.assertEqual(historico.rotulo_prey(None), "Prey não informada")

def test_salvar_sem_prey_preserva_a_gravada(self):
    reg = _reg_hist()
    h = historico.salvar({**reg, "prey": [{"tipo": "xp", "estrelas": 7}]}, self.arq)
    historico.salvar({**reg, "id": h["id"]}, self.arq)              # re-salvar sem o campo prey
    self.assertEqual(historico.obter(h["id"], self.arq)["prey"], [{"tipo": "xp", "estrelas": 7}])
    historico.salvar({**reg, "id": h["id"], "prey": []}, self.arq)  # marcar "sem prey" é explícito
    self.assertEqual(historico.obter(h["id"], self.arq)["prey"], [])

def test_aviso_prey(self):
    a, b = _h_comp("a", "A", 4, 60, 1, 4), _h_comp("b", "B", 4, 60, 1, 4)
    a["prey"], b["prey"] = [{"tipo": "xp", "estrelas": 7}], []
    self.assertIn('Prey diferente: "A" com Prey XP ★7, "B" sem prey. A XP/h não é comparável diretamente.',
                  historico.comparar([a, b])["avisos"])
    b["prey"] = [{"tipo": "xp", "estrelas": 7}]
    self.assertFalse(any("Prey" in x for x in historico.comparar([a, b])["avisos"]))
    del b["prey"]                                                    # não informada: sem aviso
    r = historico.comparar([a, b])
    self.assertFalse(any("Prey" in x for x in r["avisos"]))
    self.assertEqual(r["hunts"][1]["prey"], "Prey não informada")
```

  Também acrescente ao `test_exportar_importar` uma hunt com `prey` e confira que ela sobrevive ao importar.

- [ ] **Step 2: Rodar e ver falhar**
  - Comando: `python -m unittest test_hunt.TestPrey -v`
  - Esperado: `AttributeError: ... 'normalizar_prey'`.

- [ ] **Step 3: Implementar.**
  - `salvar`: quando `"prey" in registro`, gravar `normalizar_prey(registro["prey"])`; quando não, `if "prey" in atual: preservar["prey"] = atual["prey"]`.
  - `importar`: `if "prey" in h: h["prey"] = normalizar_prey(h["prey"])`.
  - Aviso em `comparar`: só quando **todas** as hunts têm a chave `prey` e os conjuntos `{(tipo, estrelas)}` não são todos iguais.

- [ ] **Step 4: Rodar tudo**
  - Comando: `python -m unittest`
  - Esperado: todos OK.

- [ ] **Step 5: Commit** `Historico: prey da hunt (normalizar, rotulo, preservar ao salvar, aviso no comparar)`.

---

### Task 8: Prey na API e na tela

**Files:**
- Modify: `web_api.py`: `hunt_salvar` (~473), `hunt_abrir` (~595), `hunt_historico` (~563), método novo `hunt_ultima_prey`
- Modify: `web/index.html`: linha "Prey" no Hunt Analyser (perto de `#h-salvar`, ~linha 501), `abrirHunt` (~1486), "✚ Nova hunt", card do histórico (~1458), cabeçalho do comparativo
- Test: `test_hunt.py` (`TestPrey`, testes da API)

**Interfaces:**
- Consumes: Task 7 (`normalizar_prey`, `rotulo_prey`)
- Produces:
  - `hunt_salvar(entrada, pagos=None)`: se `entrada.get("prey") is not None`, então `registro["prey"] = entrada["prey"]` (o `historico.salvar` normaliza). `prey` **não** entra na `assinatura` (ela continua só com party/solo/dano).
  - `hunt_abrir(id_)` devolve também `"prey": h.get("prey")` (pode ser `None`).
  - `hunt_historico(...)["hunts"][i]` ganha `"prey": rotulo_prey(h.get("prey"))` e `"prey_informada": "prey" in h`.
  - `hunt_ultima_prey(personagem: str) -> list | None`: a `prey` da hunt mais recente (por `ordenar`) daquele personagem (`do_personagem`) que tenha o campo. Se não houver, `None`.

- [ ] **Step 1: Escrever os testes que falham.** Com `unittest.mock.patch.object(historico, "HIST_PATH", <arquivo temporário>)` e a API criada com `object.__new__` + os atributos que `hunt_salvar` usa (`_dano_cache = {}`; se `_mesma_hunt` precisar de algo, crie também):
  - salvar com `prey=[{"tipo": "xp", "estrelas": 7}]` grava; `hunt_abrir` devolve a prey; `hunt_ultima_prey("Zandao")` devolve a mesma lista;
  - salvar de novo com `prey=None` na entrada (como faz uma hunt antiga aberta e salva) mantém a prey gravada;
  - com o histórico vazio, `hunt_ultima_prey("Zandao")` é `None`.

- [ ] **Step 2: Rodar e ver falhar**
  - Comando: `python -m unittest test_hunt.TestPrey -v`
  - Esperado: falham os testes novos.

- [ ] **Step 3: Implementar a API.**

- [ ] **Step 4: Tela.**
  - **Linha "Prey":** 3 slots, cada um com `<select>` de tipo (Nenhuma, XP, Loot, Ataque, Defesa) e `<select>` de estrelas (★1 a ★10, só visível quando o tipo não é "Nenhuma"). O estado fica em `H.entrada.prey`, que entra no `retrato()` para o botão mostrar "alterações não salvas".
  - **Regra de valor inicial** (Review Focus 1):
    - **Nova hunt** ("✚ Nova hunt" ou o primeiro colar sem `H.id`): `H.entrada.prey = await api.hunt_ultima_prey(personagem)`. Se vier `null`, todos os slots ficam em "Nenhuma" e `H.entrada.prey = []`.
    - **Abrir hunt salva:** `H.entrada.prey = e.prey` (pode ser `null`). Com `null`, os slots ficam em "Nenhuma" e aparece a dica "prey não informada nesta hunt: escolha para marcar". Enquanto o usuário não mexer em um slot, `prey` continua `null`.
    - Mexer em qualquer slot transforma `H.entrada.prey` na lista dos slots preenchidos (todos em "Nenhuma" → `[]`).
  - **Card do histórico:** um chip com `h.prey`, em `chip-neutro`, com a classe `dim` quando `!h.prey_informada`.
  - **Cabeçalho do comparativo:** `PT 4 · 1h17 · ${h.prey}`. O `cab` do backend já traz `prey` (Task 7).

- [ ] **Step 5: Verificar na tela** com o servidor de teste:
  1. nova hunt com Prey XP ★7 → salvar → o chip aparece no histórico;
  2. abrir uma hunt antiga → a dica "não informada" aparece → salvar sem mexer → o chip continua "Prey não informada";
  3. comparar uma hunt com XP e outra sem prey → o aviso aparece.

  Tirar um screenshot.

- [ ] **Step 6: Rodar tudo e commit**
  - Comando: `python -m unittest`
  - Esperado: todos OK.
  - Commit: `Hunt Analyser: marcar prey da hunt (slots, historico, comparativo)`.

---

### Task 9: Versão 1.0.6 e verificação final

**Files:**
- Modify: `versao.py` (`VERSAO_APP = "1.0.6"`), `README.md` (seção de novidades, no mesmo formato das versões anteriores)

- [ ] **Step 1:** Mudar a versão e o README.
- [ ] **Step 2:** Rodar `python -m unittest`. Esperado: todos OK, com a contagem de testes maior que antes da Task 1.
- [ ] **Step 3:** Commit `v1.0.6: precos, comparativo com ranking, prey e party por hora`.
- [ ] **Step 4: PARAR e perguntar ao usuário** se pode gerar o instalador (`instalador/gerar_instalador.ps1`) e instalar no PC dele. Publicar no GitHub (push + Release) é uma **pergunta separada**. Não fazer nenhum dos dois sem "pode".
