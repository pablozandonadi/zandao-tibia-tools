; ============================================================
; ZANDAO SIMULATED KEYS - segurar teclas repete acoes/magias no Tibia
; Requer AutoHotkey v1.1 (https://www.autohotkey.com/)
; ============================================================
;
; Alt+Shift+M : liga/desliga o macro inteiro (bipe + aviso na tela,
;       que desaparece sozinho, sem ficar fixo na tela)
; Alt+Shift+F10 : abre/fecha a janela de configuracao (toggle —
;       aperte de novo para fechar). Nela da pra adicionar, editar
;       ou remover quantas teclas quiser, escolhendo livremente
;       qual tecla fisica (ex: f, g, numpad1) e o que ela deve
;       enviar (ex: F1, F2, 3), alem do intervalo de repeticao em
;       segundos de cada uma, individualmente.
;
; Com uma tecla configurada segurada (fisicamente pressionada),
; ela envia sua tecla-alvo na hora e repete no intervalo definido,
; continuamente, ate voce soltar. Com o macro desligado (Alt+Shift+M),
; todas as teclas configuradas voltam a funcionar normalmente.
;
; O macro so age com a janela do Tibia em foco. Ao trocar pra outra
; janela (Chrome, Discord, etc.) as teclas configuradas voltam a
; funcionar normalmente sozinhas, sem precisar desligar no Alt+Shift+M
; toda vez — o Alt+Shift+M continua existindo pra quem quiser desligar
; o macro de proposito, mesmo com o Tibia em foco.
;
; As configuracoes ficam salvas em tibia_macro_config.ini, ao
; lado do script, e recarregam sozinhas na proxima vez que abrir.

#NoEnv
#SingleInstance Force
SendMode Input
SetTitleMatchMode, 2

IniFile := A_ScriptDir . "\tibia_macro_config.ini"
StartupLink := A_Startup . "\ZandaoSimulatedKeys.lnk"
; identifica pelo PROCESSO do cliente (client.exe), nao pelo titulo da
; janela: usar o titulo ("Tibia") tambem casava com abas do Chrome tipo
; "Tibia Wiki", fazendo o macro continuar ativo fora do jogo
JanelaTibia := "ahk_exe client.exe"

macroAtivo := true
configAberto := false
TeclasAtivas := {}

IniRead, numBindings, %IniFile%, Config, NumBindings, -1
Bindings := []
if (numBindings = -1)
{
    ; primeira vez rodando: cria o padrao F -> F1 a cada 1s
    Bindings.Push({tecla: "f", alvo: "F1", intervalo: 1000, pressionado: false, proximo: 0})
}
else
{
    loop, %numBindings%
    {
        idx := A_Index
        IniRead, t, %IniFile%, Config, Bind%idx%_Tecla, f
        IniRead, a, %IniFile%, Config, Bind%idx%_Alvo, F1
        IniRead, iv, %IniFile%, Config, Bind%idx%_Intervalo, 1000
        Bindings.Push({tecla: t, alvo: a, intervalo: (iv + 0), pressionado: false, proximo: 0})
    }
}

; rede de seguranca: nunca deixa a lista vazia por conta de um ini
; desatualizado/inconsistente de uma versao anterior do script
if (Bindings.Length() = 0)
    Bindings.Push({tecla: "f", alvo: "F1", intervalo: 1000, pressionado: false, proximo: 0})

AplicarHotkeys()
SetTimer, VerificarTeclas, 100

; --- Menu da bandeja ---
Menu, Tray, Tip, ZANDAO TIBIA TOOLS`nSimulated Keys
Menu, Tray, Add, Ligar/Desligar Simulated Keys (Alt+Shift+M), !+m
Menu, Tray, Add, Configurar Teclas (Alt+Shift+F10), !+F10
Menu, Tray, Add
Menu, Tray, Add, Iniciar com o Windows, ToggleAutoStart
if FileExist(StartupLink)
    Menu, Tray, Check, Iniciar com o Windows
Menu, Tray, Add

!+m::
    macroAtivo := !macroAtivo
    SoundBeep, % (macroAtivo ? 1300 : 500), 120
    if (macroAtivo)
        MostrarToast("SIMULATED KEYS LIGADO", "00E676")
    else
        MostrarToast("SIMULATED KEYS DESLIGADO", "FF5252")
return

!+F10::
    ; toggle: se ja esta aberta, a segunda apertada so fecha
    if (configAberto)
    {
        Gui, Config:Destroy
        configAberto := false
        return
    }
    configAberto := true

    Gui, Config:Destroy
    Gui, Config:Margin, 24, 18
    Gui, Config:Color, 121212, 1E1E1E

    Gui, Config:Font, s18 cA5D6A7 Bold, Segoe UI
    Gui, Config:Add, Text, w360 Center, ZANDAO TIBIA TOOLS

    Gui, Config:Font, s9 c888888 Norm, Segoe UI
    Gui, Config:Add, Text, w360 Center y+2, CONFIGURAR SIMULATED KEYS

    Gui, Config:Font, s9 c66BB6A Bold, Segoe UI
    Gui, Config:Add, Text, w360 y+20, TECLAS CONFIGURADAS (clique numa linha para selecionar)

    Gui, Config:Font, s9 cE0E0E0 Norm, Segoe UI
    Gui, Config:Add, ListView, vListaBindings w360 h150 -Multi Report y+6, Tecla|Enviar|Intervalo (s)

    Gui, Config:Font, s9 c66BB6A Bold, Segoe UI
    Gui, Config:Add, Text, w360 y+16, NOVA TECLA  (ex: f, g, numpad1)
    Gui, Config:Font, s10 cE0E0E0 Norm, Segoe UI
    Gui, Config:Add, Edit, vNovaTecla w360 Background2A2A2A y+4

    Gui, Config:Font, s9 c66BB6A Bold, Segoe UI
    Gui, Config:Add, Text, w360 y+12, O QUE ELA DEVE ENVIAR  (ex: F1, F2, 3)
    Gui, Config:Font, s10 cE0E0E0 Norm, Segoe UI
    Gui, Config:Add, Edit, vNovoAlvo w360 Background2A2A2A y+4

    Gui, Config:Font, s9 c66BB6A Bold, Segoe UI
    Gui, Config:Add, Text, w360 y+12, INTERVALO DE REPETICAO  (segundos)
    Gui, Config:Font, s10 cE0E0E0 Norm, Segoe UI
    Gui, Config:Add, Edit, vNovoIntervalo w360 Background2A2A2A y+4, 1.0

    Gui, Config:Font, s10 cE0E0E0 Bold, Segoe UI
    Gui, Config:Add, Button, xm y+20 gAdicionarBinding w114 h34, Adicionar
    Gui, Config:Add, Button, x+8 yp gEditarBinding w114 h34, Editar
    Gui, Config:Add, Button, x+8 yp gRemoverBinding w114 h34, Remover

    Gui, Config:Add, Button, xm y+8 gFecharConfig w360 h30, Fechar

    Gui, Config:Show, Center, Zandao Tibia Tools - Simulated Keys
    EstilizarControles()
    Gosub, PreencherLista
return

PreencherLista:
    ; necessario numa Gui NOMEADA: sem isso, LV_Add/LV_Delete/etc
    ; silenciosamente nao acham a ListView (ficam com 0 linhas)
    Gui, Config:Default
    Gui, ListView, ListaBindings
    LV_Delete()
    for idx, b in Bindings
        LV_Add("", b.tecla, b.alvo, Round(b.intervalo / 1000, 2))
    LV_ModifyCol(1, 90)
    LV_ModifyCol(2, 90)
    LV_ModifyCol(3, 130)
return

AdicionarBinding:
    Gui, Config:Submit, NoHide
    novaTecla := Trim(NovaTecla)
    StringLower, novaTecla, novaTecla
    novoAlvoV := Trim(NovoAlvo)

    if (novaTecla = "" || novoAlvoV = "")
    {
        MostrarToast("Preencha a tecla e o que ela deve enviar", "FFB74D")
        return
    }

    for idx, b in Bindings
    {
        if (b.tecla = novaTecla)
        {
            MostrarToast("Essa tecla ja esta configurada", "FFB74D")
            return
        }
    }

    novoSeg := NovoIntervalo + 0
    if (novoSeg < 0.1)
        novoSeg := 1.0

    Bindings.Push({tecla: novaTecla, alvo: novoAlvoV, intervalo: Round(novoSeg * 1000), pressionado: false, proximo: 0})
    Gosub, PreencherLista
    Gosub, SalvarBindings
    AplicarHotkeys()
    GuiControl,, NovaTecla,
    GuiControl,, NovoAlvo,
    MostrarToast("Tecla adicionada", "00E676")
return

EditarBinding:
    Gui, Config:Default
    Gui, ListView, ListaBindings
    linhaIdx := LV_GetNext()
    if (!linhaIdx)
    {
        MostrarToast("Selecione uma linha para editar", "FFB74D")
        return
    }
    b := Bindings[linhaIdx]
    GuiControl,, NovaTecla, % b.tecla
    GuiControl,, NovoAlvo, % b.alvo
    GuiControl,, NovoIntervalo, % Round(b.intervalo / 1000, 2)
    Bindings.RemoveAt(linhaIdx)
    Gosub, PreencherLista
    Gosub, SalvarBindings
    AplicarHotkeys()
    MostrarToast("Ajuste os campos e clique em Adicionar", "00E676")
return

RemoverBinding:
    Gui, Config:Default
    Gui, ListView, ListaBindings
    linhaIdx := LV_GetNext()
    if (!linhaIdx)
    {
        MostrarToast("Selecione uma linha para remover", "FFB74D")
        return
    }
    Bindings.RemoveAt(linhaIdx)
    Gosub, PreencherLista
    Gosub, SalvarBindings
    AplicarHotkeys()
    MostrarToast("Tecla removida", "00E676")
return

FecharConfig:
ConfigGuiClose:
ConfigGuiEscape:
    Gui, Config:Destroy
    configAberto := false
return

ToggleAutoStart:
    if FileExist(StartupLink)
    {
        FileDelete, %StartupLink%
        Menu, Tray, Uncheck, Iniciar com o Windows
        MostrarToast("Inicializacao automatica DESATIVADA", "FFB74D")
    }
    else
    {
        FileCreateShortcut, %A_ScriptFullPath%, %StartupLink%, %A_ScriptDir%
        Menu, Tray, Check, Iniciar com o Windows
        MostrarToast("Inicializacao automatica ATIVADA", "00E676")
    }
return

; Handler compartilhado por TODAS as teclas configuradas dinamicamente.
; Quando o macro esta desligado OU o Tibia nao esta em foco, reenvia a
; propria tecla (simulando o toque normal) para nao quebrar o uso dela
; fora do macro.
Bloquear:
    if (!macroAtivo || !WinActive(JanelaTibia))
    {
        tecla := A_ThisHotkey
        Hotkey, %tecla%, , Off
        Send, {%tecla%}
        Hotkey, %tecla%, , On
    }
return

VerificarTeclas:
    for idx, b in Bindings
    {
        segurando := macroAtivo && WinActive(JanelaTibia) && GetKeyState(b.tecla, "P")
        if (!segurando)
        {
            b.pressionado := false
            b.proximo := 0
        }
        else if (!b.pressionado)
        {
            b.pressionado := true
            Send, % "{" . b.alvo . "}"
            b.proximo := A_TickCount + b.intervalo
        }
        else if (A_TickCount >= b.proximo)
        {
            Send, % "{" . b.alvo . "}"
            b.proximo := A_TickCount + b.intervalo
        }
    }
return

SalvarBindings:
    IniWrite, % Bindings.Length(), %IniFile%, Config, NumBindings
    loop, % Bindings.Length()
    {
        idx := A_Index
        IniWrite, % Bindings[idx].tecla, %IniFile%, Config, Bind%idx%_Tecla
        IniWrite, % Bindings[idx].alvo, %IniFile%, Config, Bind%idx%_Alvo
        IniWrite, % Bindings[idx].intervalo, %IniFile%, Config, Bind%idx%_Intervalo
    }
return

; --- Toast escuro/verde no canto da tela, substitui o ToolTip padrao ---
MostrarToast(texto, corTexto := "00E676") {
    Gui, Toast:Destroy
    Gui, Toast:+AlwaysOnTop -Caption +ToolWindow +E0x20
    Gui, Toast:Color, 161616
    Gui, Toast:Font, s11 c%corTexto% Bold, Segoe UI
    Gui, Toast:Margin, 16, 12
    Gui, Toast:Add, Text, w260 Center, %texto%
    toastX := A_ScreenWidth - 300
    Gui, Toast:Show, x%toastX% y30 NoActivate, Toast
    SetTimer, EsconderToast, -1600
}

EsconderToast:
    Gui, Toast:Destroy
return

; Escurece a ListView e as caixas de texto: no Windows 11, controles com
; "visual styles" ativos ignoram cor de fundo customizada a menos que o
; tema do controle especifico seja desativado (SetWindowTheme "","").
; Obs: se a janela do jogo estiver em modo tela cheia EXCLUSIVA bem no
; instante em que isso roda, o Windows pode ignorar essas chamadas e a
; lista/campos ficam brancos (padrao) — nao quebra nada, so fica menos
; bonito; some ao reabrir a janela com o jogo em modo "tela cheia numa
; janela"/janela sem borda, que evita esse tipo de conflito.
EstilizarControles() {
    Gui, Config:Default
    Gui, ListView, ListaBindings
    GuiControlGet, lvHwnd, Hwnd, ListaBindings
    DllCall("uxtheme\SetWindowTheme", "Ptr", lvHwnd, "Str", "", "Str", "")
    SendMessage, 0x1001, 0, % BGR(0x1E1E1E), , ahk_id %lvHwnd%  ; LVM_SETBKCOLOR
    SendMessage, 0x1026, 0, % BGR(0x1E1E1E), , ahk_id %lvHwnd%  ; LVM_SETTEXTBKCOLOR
    SendMessage, 0x1024, 0, % BGR(0xE0E0E0), , ahk_id %lvHwnd%  ; LVM_SETTEXTCOLOR
    exStyle := 0x00000020 | 0x00010000                          ; FULLROWSELECT | DOUBLEBUFFER
    SendMessage, 0x1036, % exStyle, % exStyle, , ahk_id %lvHwnd%

    GuiControlGet, editHwnd1, Hwnd, NovaTecla
    GuiControlGet, editHwnd2, Hwnd, NovoAlvo
    GuiControlGet, editHwnd3, Hwnd, NovoIntervalo
    DllCall("uxtheme\SetWindowTheme", "Ptr", editHwnd1, "Str", "", "Str", "")
    DllCall("uxtheme\SetWindowTheme", "Ptr", editHwnd2, "Str", "", "Str", "")
    DllCall("uxtheme\SetWindowTheme", "Ptr", editHwnd3, "Str", "", "Str", "")
}

BGR(rrggbb) {
    r := (rrggbb >> 16) & 0xFF
    g := (rrggbb >> 8) & 0xFF
    b := rrggbb & 0xFF
    return (b << 16) | (g << 8) | r
}

; Sincroniza as hotkeys reais do Windows com a lista atual de Bindings:
; desliga teclas que saíram da lista, liga as que estao nela.
AplicarHotkeys() {
    global Bindings, TeclasAtivas
    for tecla, v in TeclasAtivas
    {
        encontrada := false
        for idx, b in Bindings
            if (b.tecla = tecla)
                encontrada := true
        if (!encontrada)
            Hotkey, %tecla%, , Off
    }
    novasAtivas := {}
    for idx, b in Bindings
    {
        Hotkey, % b.tecla, Bloquear, On
        novasAtivas[b.tecla] := true
    }
    TeclasAtivas := novasAtivas
}
