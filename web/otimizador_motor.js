// ---------- Optimizer da Wheel of Destiny: o motor (modelo de programação inteira resolvido pelo HiGHS) ----------
// Roda no worker (otimizador_worker.js) e no Node (testes). Não mexe na tela: recebe dados + pedido e devolve o resultado.
//
// O modelo, por fatia i da roda (custo c = 50/75/100/150/200):
//   p_i inteiro 0..c  (pontos na fatia)      f_i binário (fatia cheia: p_i >= c·f_i; só fatia cheia liga o perk)
//   - caminho até o centro: as fatias cheias formam uma árvore a partir das fatias cheias do anel 1 (fluxo: cada fatia
//     cheia "consome" 1 unidade, que só anda por fatias cheias); uma fatia parcial fora do anel 1 precisa de vizinha cheia.
//   - revelação do quadrante d = pontos do quadrante + bônus da Revelation Mastery cheia + gemas de revelação encaixadas
//     (gemas só em slot greater já liberado: 3º, 5º, 7º e 8º vessel); estágio k quando passa do limite k (250/500/1000).
// Prioridade (lexicográfica): obrigatórios > opcionais na ordem (um de cima vale mais que todos os de baixo)
//   > menos gemas de revelação usadas > metas dos pontos que sobram, na ordem > mais vessels > gastar todos os pontos.
(function (raiz) {
  'use strict';
  const STATS = ['hp', 'mana', 'capacity', 'mitigation'];

  // ---- índice dos dados de uma vocação ----
  function indexar(voc) {
    const fatias = voc.fatias, pos = new Map(fatias.map((f, i) => [f.id, i]));
    const ix = { voc, fatias, pos, viz: fatias.map((f) => f.vizinhos.map((v) => pos.get(v))), anel1: [], porDominio: new Map(),
      porPerk: new Map(), vessels: [], mastery: new Map(), greater: [] };
    voc.dominios.forEach((d) => ix.porDominio.set(d.id, []));
    fatias.forEach((f, i) => {
      if (f.anel === 1) ix.anel1.push(i);
      ix.porDominio.get(f.dominio).push(i);
      if (!ix.porPerk.has(f.perk)) ix.porPerk.set(f.perk, []);
      ix.porPerk.get(f.perk).push(i);
      if (f.tipo === 'gemVessel') ix.vessels.push(i);
      if (f.tipo === 'revelationMastery') ix.mastery.set(f.dominio, i);
    });
    voc.ordem_gemas.forEach((q, i) => { if (q === 'greater') ix.greater.push(i + 1); });   // posição do vessel que libera um slot greater
    return ix;
  }
  const limite = (ix, estagio) => (estagio > 0 ? ix.voc.estagios[estagio - 1] : 0);
  const bonusGema = (ix, grau) => ix.voc.bonus_gema[grau - 1] || 0;

  // ---- modelo em texto LP (formato CPLEX, que o HiGHS lê) ----
  class Modelo {
    constructor() { this.vars = new Map(); this.linhas = []; }
    v(nome, ub, tipo) { this.vars.set(nome, { ub, tipo }); return nome; }
    linha(termos, sentido, rhs) { this.linhas.push({ termos: termos.filter(([c]) => c !== 0), sentido, rhs }); }
    clonar() { const m = new Modelo(); m.vars = new Map(this.vars); m.linhas = this.linhas.slice(); return m; }
    lp(sentido, termos) {
      const num = (x) => (Number.isInteger(x) ? String(x) : x.toFixed(9).replace(/0+$/, '').replace(/\.$/, ''));
      const soma = (ts) => (ts.length ? ts.map(([c, n]) => `${c < 0 ? '-' : '+'} ${num(Math.abs(c))} ${n}`).join(' ') : `0 ${this.vars.keys().next().value}`);
      const out = [sentido === 'max' ? 'Maximize' : 'Minimize', ' obj: ' + soma(termos), 'Subject To'];
      this.linhas.forEach((l, i) => {
        if (!l.termos.length) { if (!(l.sentido === '<=' ? 0 <= l.rhs : l.sentido === '>=' ? 0 >= l.rhs : l.rhs === 0)) out.push(` c${i}: 0 ${this.vars.keys().next().value} >= 1`); return; }
        out.push(` c${i}: ${soma(l.termos)} ${l.sentido} ${num(l.rhs)}`);
      });
      out.push('Bounds');
      const gerais = [], binarias = [];
      for (const [n, d] of this.vars) {
        if (d.tipo === 'bin') { binarias.push(n); if (d.ub === 0) out.push(` 0 <= ${n} <= 0`); continue; }
        if (d.tipo === 'int') gerais.push(n);
        out.push(` 0 <= ${n} <= ${num(d.ub)}`);
      }
      if (gerais.length) out.push('General', ' ' + gerais.join(' '));
      if (binarias.length) out.push('Binary', ' ' + binarias.join(' '));
      out.push('End');
      return out.join('\n');
    }
  }

  // resolve e devolve {ok, obj, val: Map} ou {ok:false}
  function resolver(highs, modelo, sentido, termos) {
    const r = highs.solve(modelo.lp(sentido, termos), { output_flag: false, mip_rel_gap: 0, mip_abs_gap: 1e-7, time_limit: 20 });
    if (r.Status === 'Infeasible') return { ok: false };
    if (r.Status !== 'Optimal') throw new Error('O resolvedor parou com status ' + r.Status);
    const val = new Map();
    for (const [n, c] of Object.entries(r.Columns)) val.set(n, modelo.vars.get(n) && modelo.vars.get(n).tipo === 'cont' ? c.Primal : Math.round(c.Primal));
    return { ok: true, obj: termos.reduce((s, [c, n]) => s + c * (val.get(n) || 0), 0), val };
  }
  // fixa o melhor valor de um objetivo antes de passar para o próximo (com folga numérica mínima)
  function fixar(modelo, sentido, termos, valor) {
    if (!termos.length) return;
    const folga = 1e-6 * Math.max(1, Math.abs(valor));
    modelo.linha(termos, sentido === 'max' ? '>=' : '<=', sentido === 'max' ? valor - folga : valor + folga);
  }
  function otimizarEFixar(highs, m, sentido, termos) {
    const r = resolver(highs, m, sentido, termos);
    if (!r.ok) throw new Error('O modelo ficou impossível no meio do cálculo.');
    fixar(m, sentido, termos, r.obj);
    return r;
  }

  // ---- montagem ----
  // pedido.obrigatorio = {perks: [{perk, copias}], revelacao: {dominio: estagio}, gemas: nº mínimo de vessels, gemasRevelacao: [{dominio, grau}]}
  function montar(ix, pedido, { orcamento = pedido.pontos, comOpcionais = true } = {}) {
    const m = new Modelo(), F = ix.fatias, N = F.length, ob = pedido.obrigatorio;
    const ctx = { m, ix, p: [], f: [], g: [], opc: [] };
    F.forEach((fa, i) => { ctx.p.push(m.v('p' + i, fa.custo, 'int')); ctx.f.push(m.v('f' + i, 1, 'bin')); });
    F.forEach((fa, i) => {
      m.linha([[1, ctx.p[i]], [-fa.custo, ctx.f[i]]], '>=', 0);
      if (fa.anel !== 1) m.linha([[1, ctx.p[i]], ...ix.viz[i].map((j) => [-fa.custo, ctx.f[j]])], '<=', 0);
    });
    // fluxo: liga as fatias cheias ao centro
    const ent = F.map(() => []), sai = F.map(() => []);
    for (const i of ix.anel1) { const s = m.v('s' + i, N, 'cont'); m.linha([[1, s], [-N, ctx.f[i]]], '<=', 0); ent[i].push([1, s]); }
    F.forEach((fa, i) => ix.viz[i].forEach((j) => {
      if (F[j].anel === 1) return;
      const x = m.v(`x${i}_${j}`, N, 'cont');
      m.linha([[1, x], [-N, ctx.f[i]]], '<=', 0);
      m.linha([[1, x], [-N, ctx.f[j]]], '<=', 0);
      sai[i].push([1, x]); ent[j].push([1, x]);
    }));
    F.forEach((fa, i) => m.linha([...ent[i], ...sai[i].map(([c, n]) => [-c, n]), [-1, ctx.f[i]]], '=', 0));
    if (orcamento != null) m.linha(ctx.p.map((n) => [1, n]), '<=', orcamento);
    // gemas de revelação: g_k = 1 se a gema k está encaixada; cabem tantas quantas os slots greater liberados
    const gr = ob.gemasRevelacao || [];
    if (gr.length) {
      const y = ix.greater.map((posicao, k) => { const n = m.v('y' + k, 1, 'bin'); m.linha([...termosVessels(ctx), [-posicao, n]], '>=', 0); return n; });
      gr.forEach((_, k) => ctx.g.push(m.v('g' + k, 1, 'bin')));
      m.linha([...ctx.g.map((n) => [1, n]), ...y.map((n) => [-1, n])], '<=', 0);
    }
    // obrigatórios
    for (const pk of ob.perks || []) m.linha(termosPerk(ctx, pk.perk), '>=', pk.copias);
    for (const [d, est] of Object.entries(ob.revelacao || {})) if (est > 0) m.linha(termosRevelacao(ctx, d, pedido), '>=', limite(ix, est));
    if (ob.gemas > 0) m.linha(termosVessels(ctx), '>=', ob.gemas);
    // opcionais: o_k = 1 só se o opcional k for cumprido
    if (comOpcionais) (pedido.opcionais || []).forEach((op, k) => {
      const o = m.v('o' + k, 1, 'bin');
      if (op.tipo === 'revelacao') m.linha([...termosRevelacao(ctx, op.dominio, pedido), [-limite(ix, op.estagio), o]], '>=', 0);
      else if (op.tipo === 'gemas') m.linha([...termosVessels(ctx), [-op.n, o]], '>=', 0);
      else m.linha([[op.copias, o], ...termosPerk(ctx, op.perk).map(([c, n]) => [-c, n])], '<=', 0);
      ctx.opc.push(o);
    });
    return ctx;
  }
  const termosPerk = (ctx, perk) => (ctx.ix.porPerk.get(perk) || []).map((i) => [1, ctx.f[i]]);
  const termosVessels = (ctx) => ctx.ix.vessels.map((i) => [1, ctx.f[i]]);
  const termosPontos = (ctx) => ctx.p.map((n) => [1, n]);
  function termosRevelacao(ctx, d, pedido) {
    const ix = ctx.ix, t = (ix.porDominio.get(d) || []).map((i) => [1, ctx.p[i]]), ms = ix.mastery.get(d);
    if (ms !== undefined && ix.voc.bonus_mastery) t.push([ix.voc.bonus_mastery, ctx.f[ms]]);
    (pedido.obrigatorio.gemasRevelacao || []).forEach((gm, k) => { if (gm.dominio === d && ctx.g[k]) t.push([bonusGema(ix, gm.grau), ctx.g[k]]); });
    return t;
  }
  function termosStat(ctx, stat) {
    return ctx.ix.fatias.map((fa, i) => [fa.dedicacao[stat] || 0, ctx.p[i]]).filter(([c]) => c);
  }
  // meta "próximo estágio da revelação": nº de estágios alcançados (binários r_k)
  function termosEstagios(ctx, d, pedido, rotulo) {
    const rev = termosRevelacao(ctx, d, pedido);
    return ctx.ix.voc.estagios.map((lim, k) => { const r = ctx.m.v(`r${rotulo}_${k}`, 1, 'bin'); ctx.m.linha([...rev, [-lim, r]], '>=', 0); return [1, r]; });
  }
  function termosMeta(ctx, meta, pedido, k) {
    if (meta === 'gemas') return termosVessels(ctx);
    if (meta === 'skill') return ctx.ix.fatias.flatMap((fa, i) => (fa.tipo === 'skill' ? [[1, ctx.f[i]]] : []));
    if (meta.startsWith('perk:')) return termosPerk(ctx, meta.slice(5));
    if (meta.startsWith('revelacao:')) return termosEstagios(ctx, meta.slice(10), pedido, 'm' + k);
    if (STATS.includes(meta)) return termosStat(ctx, meta);
    return [];
  }

  // ---- fases ----
  function fasesPrioridade(highs, ctx, pedido) {
    const n = ctx.opc.length;
    if (n && n <= 30) {   // um só cálculo com pesos 2^(n-1-k): o de cima vale mais que todos os de baixo juntos
      const r = otimizarEFixar(highs, ctx.m, 'max', ctx.opc.map((o, k) => [2 ** (n - 1 - k), o]));
      ctx.opc.forEach((o) => { if (r.val.get(o) === 1) ctx.m.linha([[1, o]], '>=', 1); });
    } else for (const o of ctx.opc) otimizarEFixar(highs, ctx.m, 'max', [[1, o]]);
    if (ctx.g.length) otimizarEFixar(highs, ctx.m, 'min', ctx.g.map((n) => [1, n]));
  }
  function fasesSobras(highs, ctx, pedido) {
    (pedido.sobras || []).forEach((meta, k) => { const t = termosMeta(ctx, meta, pedido, k); if (t.length) otimizarEFixar(highs, ctx.m, 'max', t); });
    otimizarEFixar(highs, ctx.m, 'max', termosVessels(ctx));
    return otimizarEFixar(highs, ctx.m, 'max', termosPontos(ctx));
  }

  // ---- leitura de uma distribuição (também confere se ela é válida) ----
  function avaliar(ix, pontos, gemasEncaixadas = {}) {
    const F = ix.fatias, cheia = F.map((fa, i) => pontos[i] >= fa.custo), erros = [];
    const ligada = F.map(() => false), fila = ix.anel1.filter((i) => cheia[i]);
    fila.forEach((i) => { ligada[i] = true; });
    while (fila.length) { const i = fila.pop(); for (const j of ix.viz[i]) if (cheia[j] && !ligada[j]) { ligada[j] = true; fila.push(j); } }
    F.forEach((fa, i) => {
      if (pontos[i] < 0 || pontos[i] > fa.custo || !Number.isInteger(pontos[i])) erros.push(`${fa.id}: pontos fora do limite`);
      if (pontos[i] > 0 && fa.anel !== 1 && !ix.viz[i].some((j) => ligada[j])) erros.push(`${fa.id}: sem caminho até o centro`);
      if (cheia[i] && fa.anel !== 1 && !ligada[i]) erros.push(`${fa.id}: cheia mas desligada do centro`);
    });
    const copias = {};
    F.forEach((fa, i) => { if (cheia[i]) copias[fa.perk] = (copias[fa.perk] || 0) + 1; });
    const revelacao = ix.voc.dominios.map((d) => {
      let prog = ix.porDominio.get(d.id).reduce((s, i) => s + pontos[i], 0) + (gemasEncaixadas[d.id] || 0);
      const ms = ix.mastery.get(d.id);
      if (ms !== undefined && cheia[ms]) prog += ix.voc.bonus_mastery;
      return { dominio: d.id, nome: d.revelacao, progresso: prog, estagio: ix.voc.estagios.filter((l) => prog >= l).length };
    });
    const vessels = ix.vessels.filter((i) => cheia[i]).length;
    const dedicacao = Object.fromEntries(STATS.map((s) => [s, 0]));
    F.forEach((fa, i) => STATS.forEach((s) => { dedicacao[s] += (fa.dedicacao[s] || 0) * pontos[i]; }));
    dedicacao.mitigation = Math.floor(dedicacao.mitigation * 100 + 1e-8) / 100;   // o planner trunca em 2 casas
    return { valido: !erros.length, erros, gasto: pontos.reduce((a, b) => a + b, 0), copias, revelacao, vessels,
      slots: ix.voc.ordem_gemas.slice(0, vessels), danoCura: vessels, dedicacao, cheias: F.flatMap((fa, i) => (cheia[i] ? [fa.id] : [])) };
  }
  // ordem para clicar no jogo: do centro para fora pelas fatias cheias, depois as parciais
  function ordemClique(ix, pontos) {
    const F = ix.fatias, cheia = F.map((fa, i) => pontos[i] >= fa.custo), visto = F.map(() => false), ordem = [];
    const fila = ix.anel1.filter((i) => cheia[i]);
    fila.forEach((i) => { visto[i] = true; });
    for (let k = 0; k < fila.length; k++) {
      const i = fila[k];
      ordem.push({ fatia: F[i].id, pontos: pontos[i] });
      for (const j of ix.viz[i]) if (cheia[j] && !visto[j]) { visto[j] = true; fila.push(j); }
    }
    F.forEach((fa, i) => { if (pontos[i] > 0 && !visto[i]) ordem.push({ fatia: fa.id, pontos: pontos[i] }); });
    return ordem;
  }

  function lerResultado(ix, ctx, val, pedido, minimo) {
    const pontos = ctx.p.map((n) => val.get(n) || 0);
    const gr = (pedido.obrigatorio.gemasRevelacao || []).map((gm, k) => ({ ...gm, bonus: bonusGema(ix, gm.grau), encaixada: val.get(ctx.g[k]) === 1 }));
    const encaixe = {};
    gr.forEach((gm) => { if (gm.encaixada) encaixe[gm.dominio] = (encaixe[gm.dominio] || 0) + gm.bonus; });
    const av = avaliar(ix, pontos, encaixe);
    if (!av.valido) throw new Error('Distribuição inválida: ' + av.erros.join('; '));
    if (av.gasto > pedido.pontos) throw new Error('A distribuição passou do orçamento.');
    const opcionais = (pedido.opcionais || []).map((op) => {
      const feito = op.tipo === 'revelacao' ? (av.revelacao.find((r) => r.dominio === op.dominio) || {}).estagio || 0
        : op.tipo === 'gemas' ? av.vessels : av.copias[op.perk] || 0;
      const alvo = op.tipo === 'revelacao' ? op.estagio : op.tipo === 'gemas' ? op.n : op.copias;
      return { ...op, feito, ok: feito >= alvo };
    });
    return { pontos: Object.fromEntries(ix.fatias.flatMap((fa, i) => (pontos[i] ? [[fa.id, pontos[i]]] : []))), vetor: pontos,
      ordem: ordemClique(ix, pontos), ...av, livres: pedido.pontos - av.gasto, minimoObrigatorio: minimo, gemasRevelacao: gr, opcionais };
  }

  // menor nº de pontos que cumpre só os obrigatórios (null = impossível)
  function minimoPontos(highs, ix, pedido) {
    const ctx = montar(ix, pedido, { orcamento: null, comOpcionais: false });
    const r = resolver(highs, ctx.m, 'min', termosPontos(ctx));
    return r.ok ? Math.round(r.obj) : null;
  }

  // ---- cálculo principal ----
  function otimizar(highs, voc, pedido, { variantes = 3 } = {}) {
    const ix = indexar(voc);
    const ctx = montar(ix, pedido);
    if (!resolver(highs, ctx.m, 'min', []).ok) return diagnostico(highs, ix, pedido);
    fasesPrioridade(highs, ctx, pedido);
    const base = ctx.m.clonar();                 // depois dos opcionais: as variantes partem daqui
    const r = fasesSobras(highs, ctx, pedido);
    const melhor = lerResultado(ix, ctx, r.val, pedido, minimoPontos(highs, ix, pedido));
    const lista = [melhor];
    // variantes: mesma qualidade (opcionais e metas iguais), outro conjunto de fatias cheias
    const cortes = [];
    while (lista.length < variantes) {
      const cheias = new Set(lista[lista.length - 1].cheias.map((id) => ix.pos.get(id)));
      cortes.push([ctx.f.map((n, i) => (cheias.has(i) ? [-1, n] : [1, n])), 1 - cheias.size]);
      const c2 = { ...ctx, m: base.clonar() };
      cortes.forEach(([t, rhs]) => c2.m.linha(t, '>=', rhs));
      if (!resolver(highs, c2.m, 'min', []).ok) break;
      const r2 = fasesSobras(highs, c2, pedido);
      const v = lerResultado(ix, c2, r2.val, pedido, melhor.minimoObrigatorio);
      if (!mesmoNivel(melhor, v)) break;
      lista.push(v);
    }
    return { status: 'ok', ...melhor, variantes: lista };
  }
  // uma variante só vale se cumpre os mesmos opcionais
  const mesmoNivel = (a, b) => a.opcionais.every((o, k) => o.ok === b.opcionais[k].ok);

  // ---- quando os obrigatórios não cabem ----
  function diagnostico(highs, ix, pedido) {
    const minimo = minimoPontos(highs, ix, pedido), ob = pedido.obrigatorio;
    const itens = [
      ...(ob.perks || []).map((pk, k) => ({ tipo: 'perk', perk: pk.perk, copias: pk.copias, tirar: (o) => ({ ...o, perks: o.perks.filter((_, j) => j !== k) }) })),
      ...Object.entries(ob.revelacao || {}).filter(([, e]) => e > 0).map(([d, e]) => ({ tipo: 'revelacao', dominio: d, estagio: e,
        tirar: (o) => { const rv = { ...o.revelacao }; delete rv[d]; return { ...o, revelacao: rv }; } })),
      ...(ob.gemas > 0 ? [{ tipo: 'gemas', n: ob.gemas, tirar: (o) => ({ ...o, gemas: 0 }) }] : []),
    ];
    const conflitos = itens.map(({ tirar, ...item }) => {
      const sem = minimoPontos(highs, ix, { ...pedido, obrigatorio: tirar(ob) });
      return { ...item, minimoSem: sem, economia: minimo !== null && sem !== null ? minimo - sem : null };
    }).sort((a, b) => (b.economia ?? (b.minimoSem === null ? -2 : 1e9 - b.minimoSem)) - (a.economia ?? (a.minimoSem === null ? -2 : 1e9 - a.minimoSem)));
    let noMinimo = null;
    if (minimo !== null) {
      const r = otimizar(highs, ix.voc, { ...pedido, pontos: minimo }, { variantes: 1 });
      if (r.status === 'ok') noMinimo = r;
    }
    return { status: 'nao_cabe', motivo: minimo === null ? 'impossivel' : 'pontos', minimo, faltam: minimo === null ? null : minimo - pedido.pontos, conflitos, noMinimo };
  }

  // ---- quantos pontos para as próximas metas ----
  function pontosNecessarios(highs, voc, pedido, resultado) {
    const ix = indexar(voc), ob = pedido.obrigatorio, faltam = (x) => (x === null ? null : Math.max(0, x - pedido.pontos));
    const com = (o) => minimoPontos(highs, ix, { ...pedido, obrigatorio: o });
    const gemas = [];
    for (let s = Math.max(1, ob.gemas || 0); s <= ix.vessels.length; s++) {
      const min = com({ ...ob, gemas: s });
      gemas.push({ slots: s, qualidade: ix.voc.ordem_gemas[s - 1], minimo: min, faltam: faltam(min) });
    }
    const opcionais = [];
    const comoObrigatorio = (o, op) => (op.tipo === 'revelacao' ? { ...o, revelacao: { ...o.revelacao, [op.dominio]: Math.max(o.revelacao?.[op.dominio] || 0, op.estagio) } }
      : op.tipo === 'gemas' ? { ...o, gemas: Math.max(o.gemas || 0, op.n) } : { ...o, perks: [...(o.perks || []), { perk: op.perk, copias: op.copias }] });
    let acumulado = ob;
    (pedido.opcionais || []).forEach((op, k) => {
      acumulado = comoObrigatorio(acumulado, op);
      const min = com(acumulado), sozinho = k > 0 ? com(comoObrigatorio(ob, op)) : null;
      opcionais.push({ ...op, minimo: min, faltam: faltam(min), sozinho, faltamSozinho: k > 0 ? faltam(sozinho) : null });
    });
    const revelacao = [];
    const atual = resultado && resultado.status === 'ok' ? resultado.revelacao : null;
    for (const d of ix.voc.dominios) {
      const est = atual ? (atual.find((r) => r.dominio === d.id) || {}).estagio || 0 : 0, prog = atual ? (atual.find((r) => r.dominio === d.id) || {}).progresso || 0 : 0;
      const minEst = ob.revelacao?.[d.id] || 0;
      if (!prog && !minEst) continue;
      const minhas = (ob.gemasRevelacao || []).filter((g) => g.dominio === d.id).sort((a, b) => b.grau - a.grau), outras = (ob.gemasRevelacao || []).filter((g) => g.dominio !== d.id);
      for (let e = Math.max(est, minEst) + 1; e <= ix.voc.estagios.length; e++) {
        const pedir = (n) => ({ ...ob, revelacao: { ...ob.revelacao, [d.id]: e }, gemasRevelacao: [...outras, ...minhas.slice(0, n)] });
        const min = com(pedir(0)), comGemas = [];
        let melhor = min;
        for (let n = 1; n <= minhas.length; n++) {
          const m2 = com(pedir(n));
          if (m2 !== null && (melhor === null || m2 < melhor)) { melhor = m2; comGemas.push({ gemas: n, bonus: minhas.slice(0, n).reduce((s, g) => s + bonusGema(ix, g.grau), 0), minimo: m2, faltam: faltam(m2) }); }
        }
        revelacao.push({ dominio: d.id, nome: d.revelacao, estagio: e, minimo: min, faltam: faltam(min), comGemas });
      }
    }
    return { gemas, opcionais, revelacao };
  }

  // código da roda nova (W26) a partir da distribuição: posição de cada fatia no planner novo (campo w26 dos dados)
  function codigoW26(vocNome, voc, vetor, pontosPromocao) {
    const pts = Array(36).fill(0);
    voc.fatias.forEach((fa, i) => { pts[fa.w26] = vetor[i] || 0; });
    const json = JSON.stringify({ vocation: vocNome, promotionPoints: pontosPromocao, points: pts });
    const b64 = typeof btoa === 'function' ? btoa(json) : Buffer.from(json, 'utf8').toString('base64');
    return 'W26.' + b64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  const api = { indexar, avaliar, ordemClique, otimizar, pontosNecessarios, codigoW26, STATS };
  if (typeof module === 'object' && module.exports) module.exports = api;
  raiz.OtimizadorRoda = api;
})(typeof self !== 'undefined' ? self : globalThis);
