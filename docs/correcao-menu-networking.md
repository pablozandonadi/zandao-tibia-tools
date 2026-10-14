# Menu Networking e atualização da interface

A captura enviada em 14/10/2026 mostrava a Beta 52 com um menu anterior, sem Rede. Foi verificado que tanto o commit publicado quanto o index.html da instalação Beta continham a entrada Rede. A evidência aponta para uma interface antiga carregada em execução; não foi possível inspecionar o DOM daquela janela para confirmar a causa exata.

A inicialização passa a usar um perfil WebView separado por versão em webview_session/<versão>, preservando o perfil anterior e os dados JSON do aplicativo. Assim, uma atualização não reutiliza o cache do navegador da versão anterior. O menu agora se chama explicitamente Networking, entre Guild Stats e Configurações.

Um teste de inicialização verifica que duas versões usam perfis diferentes dentro da pasta de dados. As demais alterações da Beta 52, incluindo a rotina de prints, foram preservadas na cópia de publicação.
