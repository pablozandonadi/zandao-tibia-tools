# Brasil Hits no Tibia Tudo — plano de integração

Data: 14/10/2026. Escopo desta entrega: investigação e plano; implementação pendente.

## Ferramentas e limites

REA utilizado para capturar o site público e suas respostas em Chromium. Superpowers não foi localizado no catálogo de ferramentas, nas skills locais ou nos plugins pesquisados em .claude, .agents e .codex/plugins. Há planos anteriores em docs/superpowers, mas isso não fornece a skill. Este plano foi preparado manualmente; não representa execução do Superpowers.

## Evidências

- REA: ev_d60c549f7d3dffd85d660c87740df406f56349099d8f0d3780039bf8101c4bff. Navegação em https://www.brasilhits.com/ com perfil vazio, sem login, espera de três segundos e captura de respostas. API /api/stations e /api/np/pop responderam HTTP 200. Requisições contínuas /api/feed ficaram abertas ao fim da janela; cobertura limitada ao período observado.
- /api/stations: SHA-256 cf304a8173fe222e1aa92325398475a3454c6bdab83d0010f5e0382a37fe1501. O catálogo retorna stations, com id, slug, label, maintenance, cover, streamUrl, streamUrlLow e qualities.
- Oito canais observados: Pop, Sertanejo, Pagode, Rock, Dance, Flashback, Latino e Gospel.
- /api/np/pop retorna current.title, current.artist, current.art, history, isOnline, maintenance, elapsed e duration. A falha de metadados deve ser independente do áudio.
- /stream-url.js?v=7: SHA-256 bcee78927ea7f25bc8df70a932fe9aa0f7fc861403eeff3f8f51f89547d166e0. Código capturado mostra o padrão https://live.brasilhits.com/listen/{slug}/acc, substituição pelas URLs configuradas e suporte a qualidades. Campo streamUrl vazio não significa canal sem transmissão.
- Pop, Sertanejo, Pagode e Flashback anunciam 32 e 64 kbps. Gospel anuncia 64 kbps. Rock, Dance e Latino não anunciam qualities nessa resposta; não inventar opções de qualidade para esses canais.
- Uma segunda captura REA clicou no botão Tocar e registrou /listen/brasilhits-pop/acc com resposta audio/aac, 64 kbps, 44100 Hz e dois canais. Cabeçalho Access-Control-Allow-Origin observado: https://www.brasilhits.com. Essa operação retornou cleanup_incomplete, com observação parcial e encerramento do perfil/transporte não confirmado. Não repetir sem verificar os recursos reportados. Não há comprovação de som audível nem de compatibilidade no aplicativo.

## Solução recomendada

Player próprio na interface HTML existente, com um único HTMLAudioElement persistente. Python consulta e normaliza catálogo/metadados através da ponte do PyWebView; áudio é recebido diretamente pelo elemento de mídia, sem crossorigin e sem Web Audio na primeira versão. Reprodução cross-origin de mídia precisa ser validada no WebView2; o CORS observado não permite concluir que essa reprodução será bloqueada.

Adicionar entrada Rádio no menu e um controle compacto persistente com canal, tocar/parar, volume e estado. Trocar de página não deve recriar o áudio. Iniciar parado, lembrar canal e volume, não iniciar transmissão automaticamente ao abrir o aplicativo. Minimizar deve manter a reprodução; fechar de verdade deve encerrá-la. Volume da rádio independente dos timers e alertas.

Não embutir a página remota com acesso à API Python. Não executar scripts remotos na interface privilegiada. Não copiar o player/site: implementar controles próprios e um link para o site oficial. Login, pedidos de músicas, votação, gravação e letras ficam fora da primeira versão.

## Etapa 1 — prova de compatibilidade (bloqueia a escolha final do transporte)

- [ ] Criar experimento isolado PyWebView/WebView2 com botão de ação humana e áudio Pop: https://live.brasilhits.com/listen/brasilhits-pop/acc.
- [ ] Verificar playing, avanço da mídia e som audível no Windows, pausa, retomada ao vivo, volume, minimização e troca de página.
- [ ] Confirmar resposta e codec para os demais canais; não declarar os oito funcionais com base apenas no catálogo.
- [ ] Validar metadados via Python sem depender de CORS do documento local.
- [ ] Se áudio direto falhar, identificar causa (codec, origem, servidor ou runtime). Avaliar transporte/backend dedicado somente com essa evidência. Não incluir VLC/FFmpeg antes de demonstrar necessidade.

## Etapa 2 — catálogo e metadados

Arquivos propostos: radio_brasilhits.py, test_radio_brasilhits.py; extensão pontual de web_api.py.

- [ ] Implementar cliente HTTP de leitura para /api/stations e /api/np/{id}, com timeout e limites de resposta, sem bloquear a interface.
- [ ] Normalizar campos e tratar JSON inválido, manutenção, ausência de capa, streamUrl vazio e qualities vazias.
- [ ] Resolver URL: qualidade válida selecionada; senão streamUrl; senão padrão /listen/{slug}/acc observado no código do site. Validar slug e HTTPS, hostname e redirecionamentos. Novos hosts não confiáveis devem exigir ajuste explícito da integração.
- [ ] Aceitar somente IDs do catálogo normalizado nos métodos da ponte; não oferecer fetch arbitrário por URL à interface.
- [ ] Cache de catálogo em memória; atualizar ao entrar na Rádio ou reconectar, com intervalo mínimo. Não consultar todas as músicas de todos os canais continuamente.
- [ ] Consultar música do canal ativo a cada 15 segundos enquanto reproduz, sem sobreposição; falha não interrompe áudio. Exibir texto com textContent.
- [ ] Testar respostas simuladas: catálogo observado, fallback, manutenção, URLs inválidas, timeout e metadados ausentes. Os testes não dependem do site ao vivo.

## Etapa 3 — controles e reprodução

Arquivos propostos: web/radio.js e web/radio.css; alterações pontuais em web/index.html (menu, seção e irPara).

- [ ] Implementar singleton de áudio com estados parado, conectando, tocando, reconectando e indisponível. Confirmar tocando somente pelo evento playing.
- [ ] Tratar rejeição de play(), error, stalled e falta de progresso com timeout. Parar libera src e conexão; retomar abre transmissão ao vivo.
- [ ] Trocar canal interrompe conexão anterior e invalida respostas antigas de metadados.
- [ ] Reconectar com espera crescente e limite de tentativas, mantendo intenção do usuário. Parar cancela todas as tentativas; nunca reconectar depois de parada manual.
- [ ] Exibir os oito canais do catálogo, qualidade apenas quando anunciada, nome da música/artista, botão Abrir site e controles acessíveis por teclado.
- [ ] Garantir um único áudio ao navegar entre páginas, layout normal/gadget, volume independente e ausência de conflito com atalhos do Tibia.
- [ ] Persistir somente canal, qualidade e volume pelo padrão existente de preferências, respeitando app_paths.py e isolamento Beta/estável. Não salvar tokens, histórico musical ou estado tocando.

## Etapa 4 — validação e Beta oficial

- [ ] Testar máquina de estados: troca rápida de canal, respostas fora de ordem, parada durante reconexão e tentativas esgotadas.
- [ ] Validar manualmente WebView2 real: canais, internet desconectada/restaurada, rádio indisponível, timers simultâneos, minimização/tray, fechamento e reabertura.
- [ ] Conferir inclusão de radio.js/radio.css pelo empacotamento e manifesto de recursos, conforme packaging-resources.json e verificações existentes.
- [ ] Executar testes relevantes e verificações obrigatórias do pipeline. Preservar branch e alterações em andamento na pasta compartilhada.
- [ ] Publicar apenas arquivos da integração por cópia temporária em develop, conforme docs/pipeline-beta.md e AGENTS.md. Não levar dados pessoais.
- [ ] Aguardar publish-beta.yml e confirmar instalador, portátil e manifestos da prerelease. Informar versão e link da Beta. Não promover main/estável automaticamente.

## Critérios de conclusão

Rádio audível na instalação Beta, controles funcionais, troca de páginas e minimização sem interrupção, sem reprodução automática ao abrir, sem sobreposição de canais, sem reconexão após parada manual, sem alterar volume dos timers, falha de metadados sem interromper áudio, e artefatos oficiais disponíveis. Compatibilidade de AAC/WebView2, comportamento de todos os canais e estabilidade prolongada permanecem pendentes de implementação e teste.
