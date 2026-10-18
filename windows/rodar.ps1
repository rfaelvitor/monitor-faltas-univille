# Chamado pelo Agendador de Tarefas (via rodar.vbs, sem janela).
# Pra rodar na mao e forcar uma nova verificacao: powershell -ExecutionPolicy Bypass -File rodar.ps1 -Forcar
param([switch]$Forcar)
$ProgressPreference = "SilentlyContinue"
$base = Join-Path $env:USERPROFILE ".monitor-faltas"
$codigo = Join-Path $base "codigo"
$log = Join-Path $base "logs\ultima-execucao.log"
"=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Out-File $log -Encoding utf8

# atualiza o codigo pelo zip do branch main; sem internet ou com erro segue com o que ja tem
try {
    $repo = (Select-String -Path (Join-Path $base ".env") -Pattern "^GITHUB_REPO=(.+)$").Matches[0].Groups[1].Value.Trim()
    $zip = Join-Path $env:TEMP "monitor-faltas.zip"
    $tmp = Join-Path $env:TEMP "monitor-faltas-extraido"
    Invoke-WebRequest "https://codeload.github.com/$repo/zip/refs/heads/main" -OutFile $zip -UseBasicParsing -TimeoutSec 60
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Expand-Archive $zip $tmp -Force
    $novo = (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName
    Remove-Item $codigo -Recurse -Force
    Move-Item $novo $codigo
    "codigo atualizado" | Out-File $log -Append -Encoding utf8
} catch {
    "sem atualizar o codigo: $($_.Exception.Message)" | Out-File $log -Append -Encoding utf8
}

$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) { $uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe" }
$env:PYTHONUTF8 = "1"
if ($Forcar) { $env:FORCAR = "1" }

Set-Location $codigo
cmd /c "`"$uv`" run --python 3.12 --with-requirements requirements.txt python -m playwright install chromium >> `"$log`" 2>&1"
cmd /c "`"$uv`" run --python 3.12 --with-requirements requirements.txt python -m faltas >> `"$log`" 2>&1"
"=== fim, codigo de saida $LASTEXITCODE ===" | Out-File $log -Append -Encoding utf8
exit $LASTEXITCODE
