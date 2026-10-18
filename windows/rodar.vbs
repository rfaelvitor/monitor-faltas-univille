' Chamado pelo Agendador. O PowerShell abre minimizado e sem roubar o foco:
' com janela totalmente oculta o navegador herdava o modo oculto e travava
Set sh = CreateObject("WScript.Shell")
base = sh.ExpandEnvironmentStrings("%USERPROFILE%") & "\.monitor-faltas"
sh.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & base & "\rodar.ps1""", 7, True
