' Chamado pelo Agendador a cada 30 minutos. Roda sem janela porque não abre navegador
Set sh = CreateObject("WScript.Shell")
base = sh.ExpandEnvironmentStrings("%USERPROFILE%") & "\.monitor-faltas"
sh.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & base & "\codigo\windows\manter-sessao.ps1""", 0, True
