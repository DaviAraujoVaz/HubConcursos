# Roda um comando do ConcursoHub (por padrão, a rotina: coleta + resumo de avisos)
# e acrescenta a saída em dados\logs\rotina.log. É o que a tarefa do Agendador
# do Windows chama; também dá para rodar à mão:
#   powershell -ExecutionPolicy Bypass -File scripts\rotina.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\rotina.ps1 -Comando "avisar --previa"
param([string]$Comando = "rotina")

$ErrorActionPreference = "Continue"
$projeto = Split-Path -Parent $PSScriptRoot
Set-Location $projeto

$logs = Join-Path $projeto "dados\logs"
New-Item -ItemType Directory -Force $logs | Out-Null
$log = Join-Path $logs "rotina.log"
# Guarda só o log atual e o anterior.
if ((Test-Path $log) -and (Get-Item $log).Length -gt 10MB) {
    Move-Item -Force $log "$log.1"
}

# Saída do Python em UTF-8, para os acentos chegarem certos ao log.
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$python = Join-Path $projeto ".venv\Scripts\python.exe"
$argumentos = @("manage.py") + ($Comando -split "\s+")
"=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') manage.py $Comando ===" | Out-File -Append -Encoding utf8 $log
# No PowerShell 5.1, cada linha do stderr vira um ErrorRecord; o texto original fica em TargetObject.
& $python @argumentos 2>&1 |
    ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { "$($_.TargetObject)" } else { "$_" } } |
    Out-File -Append -Encoding utf8 $log
"=== fim (código $LASTEXITCODE) ===" | Out-File -Append -Encoding utf8 $log
