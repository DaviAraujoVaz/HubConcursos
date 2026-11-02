# Cria (ou recria) a tarefa "ConcursoHub - rotina" no Agendador de Tarefas do
# Windows. Ela roda scripts\rotina.ps1 a cada 3 horas e também 5 minutos depois
# do logon. Se o PC estava desligado no horário, roda assim que possível.
#
# Rode uma vez, no PowerShell, a partir da pasta do projeto:
#   powershell -ExecutionPolicy Bypass -File scripts\agendar_rotina.ps1
# Para remover:
#   Unregister-ScheduledTask -TaskName "ConcursoHub - rotina"
param([int]$IntervaloHoras = 3)

$ErrorActionPreference = "Stop"
$projeto = Split-Path -Parent $PSScriptRoot
$script = Join-Path $PSScriptRoot "rotina.ps1"
$nome = "ConcursoHub - rotina"

if (-not (Test-Path (Join-Path $projeto ".venv\Scripts\python.exe"))) {
    throw "Não achei .venv\Scripts\python.exe em $projeto. Crie o ambiente virtual antes."
}

$acao = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`"" `
    -WorkingDirectory $projeto
$repeticao = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) `
    -RepetitionInterval (New-TimeSpan -Hours $IntervaloHoras)
$logon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$logon.Delay = "PT5M"
# StartWhenAvailable: recupera a rodada perdida com o PC desligado.
# IgnoreNew: se uma coleta longa ainda estiver rodando, não começa outra.
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 12)

Register-ScheduledTask -TaskName $nome -Action $acao -Trigger @($repeticao, $logon) -Settings $config `
    -Description "Coleta as fontes do ConcursoHub e envia o resumo diário de avisos." -Force | Out-Null

Write-Host "Tarefa '$nome' criada: a cada $IntervaloHoras h e 5 min depois do logon."
Write-Host "Log em: $(Join-Path $projeto 'dados\logs\rotina.log')"
