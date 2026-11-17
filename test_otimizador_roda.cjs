// Teste do motor do Optimizer da roda com o HiGHS de verdade. Rodar: node test_otimizador_roda.cjs (o test_otimizador_roda.py chama).
const assert = require('assert');
const path = require('path');
const dados = require('./web/roda_otimizador.json');
const M = require('./web/otimizador_motor.js');
const carregar = require('./web/vendor/highs/highs.js');

const pedido = (extra = {}) => ({ pontos: 500, obrigatorio: { perks: [], revelacao: {}, gemas: 0, gemasRevelacao: [] }, opcionais: [], sobras: [], ...extra });

(async () => {
  const highs = await carregar({ locateFile: (f) => path.join(__dirname, 'web', 'vendor', 'highs', f) });
  const sorc = dados.vocacoes.sorcerer, ix = M.indexar(sorc);

  // 1) sem exigências: gasta tudo, distribuição válida, ordem de clique cobre todas as fatias com pontos
  let r = M.otimizar(highs, sorc, pedido());
  assert.strictEqual(r.status, 'ok');
  assert.strictEqual(r.gasto, 500);
  assert.ok(M.avaliar(ix, r.vetor).valido);
  assert.strictEqual(r.ordem.reduce((s, o) => s + o.pontos, 0), 500);

  // 2) obrigatórios cumpridos: 4 vessels + Beam Mastery (top-right) estágio 1
  r = M.otimizar(highs, sorc, pedido({ pontos: 1000, obrigatorio: { perks: [], revelacao: { 'top-right': 1 }, gemas: 4, gemasRevelacao: [] } }));
  assert.strictEqual(r.status, 'ok');
  assert.ok(r.vessels >= 4);
  assert.ok(r.revelacao.find((x) => x.dominio === 'top-right').estagio >= 1);
  assert.ok(r.minimoObrigatorio <= 1000 && r.minimoObrigatorio > 0);

  // 3) não cabe: estágio III nas quatro revelações com 300 pontos -> diz quanto falta e o que mais pesa
  r = M.otimizar(highs, sorc, pedido({ pontos: 300, obrigatorio: { perks: [], revelacao: { 'top-left': 3, 'top-right': 3, 'bottom-left': 3, 'bottom-right': 3 }, gemas: 0, gemasRevelacao: [] } }));
  assert.strictEqual(r.status, 'nao_cabe');
  assert.strictEqual(r.motivo, 'pontos');
  assert.ok(r.faltam > 0 && r.minimo === 300 + r.faltam);
  assert.ok(r.conflitos.length === 4 && r.conflitos[0].economia > 0);

  // 4) prioridade dos opcionais: com poucos pontos, o de cima ganha mesmo que o de baixo seja mais barato
  const caro = { tipo: 'revelacao', dominio: 'bottom-left', estagio: 1 }, barato = { tipo: 'revelacao', dominio: 'top-left', estagio: 1 };
  r = M.otimizar(highs, sorc, pedido({ pontos: 260, opcionais: [caro, barato] }));
  assert.strictEqual(r.opcionais[0].ok, true);
  r = M.otimizar(highs, sorc, pedido({ pontos: 260, opcionais: [barato, caro] }));
  assert.strictEqual(r.opcionais[0].ok, true);

  // 5) gema de revelação greater só encaixa com slot greater liberado (3º vessel) e encurta o caminho
  const sem = M.otimizar(highs, sorc, pedido({ pontos: 2000, obrigatorio: { perks: [], revelacao: { 'top-left': 3 }, gemas: 0, gemasRevelacao: [] } })).minimoObrigatorio;
  const com = M.otimizar(highs, sorc, pedido({ pontos: 2000, obrigatorio: { perks: [], revelacao: { 'top-left': 3 }, gemas: 0, gemasRevelacao: [{ dominio: 'top-left', grau: 4 }] } }));
  assert.ok(com.minimoObrigatorio <= sem);
  if (com.gemasRevelacao[0].encaixada) assert.ok(com.vessels >= 3);

  // 6) pontos necessários e variantes
  const base = pedido({ pontos: 600, opcionais: [{ tipo: 'perk', perk: 'augmented-energy-wave', copias: 2 }], sobras: ['gemas', 'hp'] });
  r = M.otimizar(highs, sorc, base);
  const pn = M.pontosNecessarios(highs, sorc, base, r);
  assert.strictEqual(pn.gemas.length, 8);
  assert.ok(pn.gemas.every((g, k) => k === 0 || g.minimo >= pn.gemas[k - 1].minimo));   // mais slots nunca custam menos
  assert.ok(r.variantes.length >= 1 && r.variantes.every((v) => M.avaliar(ix, v.vetor).valido));

  // 7) código W26: cada fatia vai para a posição certa do planner novo
  const cod = M.codigoW26('sorcerer', sorc, r.vetor, 600);
  const j = JSON.parse(Buffer.from(cod.slice(4).replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString());
  assert.strictEqual(j.vocation, 'sorcerer');
  assert.strictEqual(j.points.reduce((a, b) => a + b, 0), r.gasto);
  sorc.fatias.forEach((fa, i) => assert.strictEqual(j.points[fa.w26], r.vetor[i]));

  // 8) as 5 vocações resolvem
  for (const v of Object.keys(dados.vocacoes)) assert.strictEqual(M.otimizar(highs, dados.vocacoes[v], pedido(), { variantes: 1 }).status, 'ok');
  console.log('OK otimizador');
})().catch((e) => { console.error(e); process.exit(1); });
