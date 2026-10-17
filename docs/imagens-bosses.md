# Imagens dos bosses (Bosstiary / Boss Cooldowns)

Data: 17/10/2026. As telas mostravam "?" porque só 120 dos 539 bosses do `boss_catalog.py` tinham GIF em `web/assets/creatures/`.

## Como foi feito

`baixar_imagens_bosses.py` (só biblioteca padrão) calcula os bosses sem arquivo, resolve a URL real pela API MediaWiki
(`action=query&prop=imageinfo&iiprop=url`, User-Agent `TibiaTudo-bossimages/1.0`, lotes de 50 títulos, 1,1 s entre chamadas,
0,4 s entre downloads, sem paralelismo) e baixa `File:<Nome do boss>.gif`. O nome do arquivo segue a regra de `bossImage`
em `web/assistente.js` (nome sem " (...)", minúsculas, sequências fora de a-z0-9 viram `_`). Fonte principal: TibiaWiki BR
(https://www.tibiawiki.com.br), a mesma de `task_item_images.py`; fallback: TibiaWiki EN (tibia.fandom.com).
Cada GIF é validado: HTTP 200, começa com `GIF8`, entre 200 B e 300 KB. É idempotente e nunca sobrescreve arquivos.
Para repetir: `python -X utf8 -B baixar_imagens_bosses.py` (`--dry-run` só lista; `--relatorio x.json` salva o resultado).

## Resultado

| | Quantidade |
|---|---|
| Bosses no catálogo | 539 |
| Já tinham imagem (ignorados) | 120 |
| Arquivos baixados (TibiaWiki BR) | 395 (cobrem 402 bosses; variantes como "X (Criatura)" usam o mesmo arquivo) |
| Sem imagem na wiki / bloqueados | 11 arquivos (17 bosses) |
| Bosses com imagem agora | 522 de 539 |

Os 395 arquivos foram adicionados a `packaging-resources.json` (o empacotamento exige cada arquivo de `web/` na lista).
`web/assets/creatures.json` não foi alterado de propósito: ele alimenta a busca de criaturas da hunt, que não deve passar a listar bosses.

## Bosses ainda sem imagem

Seguem exibindo "?" (a interface já trata o erro de carregamento):
Chayenne, Count Tofifti, Denson Larika, Lionet, Mirade, Skyrr, The First Dragon e as Timedisplaced Anomaly
(Great Roshamuul; Major Fiehonja, Issavi e Rascacoon; Minor Ankrahmun, Rookgaard e Thais; Banuta, Warzone I e Zao).
Chayenne, Denson Larika, Great Timedisplaced Anomaly, Mirade e The First Dragon existem só na wiki EN, cujo CDN respondeu 403
ao download automático; os demais não têm GIF com esse nome em nenhuma das duas wikis.

## Licença e atribuição

Os sprites são arte do Tibia, propriedade da CipSoft GmbH, usados como nas demais imagens do app (itens de `web/assets/items`
vêm da mesma TibiaWiki). O conteúdo da TibiaWiki é publicado sob CC BY-SA; a origem de cada arquivo é a página `File:<nome>.gif`
da TibiaWiki BR. O projeto não tem arquivo de licenças/créditos para as imagens de criaturas (os 996 GIFs anteriores vieram de
uma pasta local do TibiaVision, ver `docs/criaturas-da-hunt.md`), por isso a atribuição fica registrada aqui.
O app não é afiliado à CipSoft nem à TibiaWiki.
