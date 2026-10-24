# Chamado a cada 30 minutos pelo Agendador (via manter-sessao.vbs, sem janela). Não abre navegador.
$base = Join-Path $env:USERPROFILE ".monitor-faltas"
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) { $uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe" }
$env:PYTHONUTF8 = "1"
Set-Location (Join-Path $base "codigo")
& $uv run --python 3.12 --with-requirements requirements.txt python -m faltas.manter_sessao 2>&1 | ForEach-Object { "$_" } | Out-File (Join-Path $base "logs\manter-sessao.log") -Encoding utf8
