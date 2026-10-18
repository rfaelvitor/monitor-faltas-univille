# Instala o monitor de faltas no Agendador de Tarefas do Windows.
# Uso (PowerShell normal, sem administrador):
#   $env:MONITOR_REPO="SEU_USUARIO/SEU_REPO"; irm https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPO/main/windows/instalar.ps1 | iex
# Rodar de novo atualiza tudo e mantem a configuracao (.env) que ja existe.
# sem bloco param: o script roda via irm | iex
$Repo = if ($env:MONITOR_REPO) { $env:MONITOR_REPO } else { "rfaelvitor/monitor-faltas-univille" }
$Horario = if ($env:MONITOR_HORARIO) { $env:MONITOR_HORARIO } else { "08:00" }
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$base = Join-Path $env:USERPROFILE ".monitor-faltas"
$codigo = Join-Path $base "codigo"
$envArq = Join-Path $base ".env"
$tarefa = "Monitor de faltas Univille"
New-Item -ItemType Directory -Force -Path $base, (Join-Path $base "logs") | Out-Null

Write-Host ""
Write-Host "== Monitor de faltas Univille ==" -ForegroundColor Cyan
Write-Host "Repositorio: $Repo   Horario diario: $Horario"

# 1. uv (baixa um Python portatil, sem instalador)
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) {
    Write-Host "Instalando uv..."
    powershell -NoProfile -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex" | Out-Null
    $uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (-not (Test-Path $uv)) { throw "Nao achei o uv depois de instalar. Feche e abra o PowerShell e rode de novo." }
}

# 2. codigo
Write-Host "Baixando o codigo..."
$zip = Join-Path $env:TEMP "monitor-faltas.zip"
$tmp = Join-Path $env:TEMP "monitor-faltas-extraido"
Invoke-WebRequest "https://codeload.github.com/$Repo/zip/refs/heads/main" -OutFile $zip -UseBasicParsing
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive $zip $tmp -Force
Remove-Item $codigo -Recurse -Force -ErrorAction SilentlyContinue
Move-Item (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName $codigo
Copy-Item (Join-Path $codigo "windows\rodar.ps1"), (Join-Path $codigo "windows\rodar.vbs") $base -Force

# 3. configuracao
function Perguntar($texto, [switch]$Secreto, $padrao = "") {
    if ($Secreto) {
        $s = Read-Host $texto -AsSecureString
        return [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
    }
    $v = Read-Host "$texto$(if ($padrao) { " [$padrao]" })"
    if (-not $v) { $v = $padrao }
    return $v
}

if (Test-Path $envArq) {
    Write-Host "Configuracao existente mantida em $envArq"
} else {
    Write-Host ""
    Write-Host "Configuracao (fica so neste computador, em $envArq)" -ForegroundColor Cyan
    $dono, $nome = $Repo.Split("/")
    $linhas = @(
        "UNIVILLE_USUARIO=$(Perguntar 'Matricula do portal')",
        "UNIVILLE_SENHA=$(Perguntar 'Senha do portal' -Secreto)",
        "SENHA_PAINEL=$(Perguntar 'Senha do painel (use a mesma de antes, se ja tinha)' -Secreto)",
        "GMAIL_USUARIO=$(Perguntar 'Seu Gmail')",
        "GMAIL_SENHA_APP=$(Perguntar 'Senha de app do Gmail' -Secreto)",
        "GITHUB_TOKEN=$(Perguntar 'Token do GitHub (Contents read/write neste repo)' -Secreto)",
        "GITHUB_REPO=$Repo",
        "URL_PAINEL=https://$dono.github.io/$nome/",
        "HEADLESS=0",
        "UMA_VEZ_POR_DIA=1",
        "PASTA_SAIDA=$(Join-Path $base 'site')"
    )
    [IO.File]::WriteAllText($envArq, ($linhas -join "`r`n") + "`r`n", (New-Object Text.UTF8Encoding $false))
    Write-Host "Configuracao salva."
}

# 4. dependencias (primeira vez demora uns minutos)
Write-Host "Preparando Python e navegador..."
Push-Location $codigo
& $uv run --python 3.12 --with-requirements requirements.txt python -m playwright install chromium | Out-Null
Pop-Location

# 5. tarefa agendada: todo dia no horario; se o PC estiver desligado, roda assim que voce ligar
$acao = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$(Join-Path $base 'rodar.vbs')`""
$gatilho = New-ScheduledTaskTrigger -Daily -At $Horario
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew
$quem = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $tarefa -Action $acao -Trigger $gatilho -Settings $config -Principal $quem -Force | Out-Null
Write-Host "Tarefa '$tarefa' criada: todo dia as $Horario (ou ao ligar o PC, se perdeu o horario)." -ForegroundColor Green

# 6. runner antigo do GitHub Actions, se existir
$atalho = Join-Path ([Environment]::GetFolderPath("Startup")) "runner-faltas.cmd"
if (Test-Path $atalho) {
    if ((Read-Host "Encontrei o runner antigo do GitHub na inicializacao. Remover? (S/n)") -ne "n") {
        Remove-Item $atalho -Force
        Get-Process Runner.Listener, Runner.Worker -ErrorAction SilentlyContinue | Stop-Process -Force
        Write-Host "Runner removido da inicializacao. Pode apagar a pasta C:\actions-runner quando quiser."
    }
}

if ((Read-Host "Rodar uma verificacao agora? (S/n)") -ne "n") {
    Start-ScheduledTask -TaskName $tarefa
    Write-Host "Rodando. Uma janela do navegador vai abrir; se aparecer o desafio de imagens, resolva nela."
    Write-Host "Log: $(Join-Path $base 'logs\ultima-execucao.log')"
}
