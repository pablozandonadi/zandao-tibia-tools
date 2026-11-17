// Worker do Optimizer da roda: carrega o HiGHS (WebAssembly, licença MIT em vendor/highs) e roda o motor fora da tela,
// para a interface não travar enquanto o resolvedor trabalha.
importScripts('vendor/highs/highs.js', 'otimizador_motor.js');
let highs = null;
self.onmessage = async (e) => {
  const { id, tipo, vocacao, voc, pedido, resultado } = e.data;
  try {
    highs = highs || Module({ locateFile: (f) => 'vendor/highs/' + f });
    const h = await highs;
    const r = tipo === 'pontos' ? OtimizadorRoda.pontosNecessarios(h, voc, pedido, resultado) : OtimizadorRoda.otimizar(h, voc, pedido);
    if (r.status === 'ok') r.codigo = OtimizadorRoda.codigoW26(vocacao, voc, r.vetor, pedido.pontos);
    if (r.status === 'ok') r.variantes.forEach((v) => { v.codigo = OtimizadorRoda.codigoW26(vocacao, voc, v.vetor, pedido.pontos); });
    if (r.noMinimo) r.noMinimo.codigo = OtimizadorRoda.codigoW26(vocacao, voc, r.noMinimo.vetor, r.minimo);
    self.postMessage({ id, ok: true, r });
  } catch (err) {
    highs = null;   // um erro do WebAssembly pode deixar o resolvedor quebrado: recarrega no próximo pedido
    self.postMessage({ id, ok: false, erro: String((err && err.message) || err) });
  }
};
