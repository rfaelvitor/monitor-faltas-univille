' Abre o rodar.ps1 sem janela de terminal (o Agendador chama este arquivo)
Set sh = CreateObject("WScript.Shell")
base = sh.ExpandEnvironmentStrings("%USERPROFILE%") & "\.monitor-faltas"
sh.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & base & "\rodar.ps1""", 0, True
