# 计划任务：每分钟检查一次「WPS 在跑但引擎没在跑」→ 拉起引擎
#
# 为什么用计划任务而不是常驻看门狗：用户要求不常驻。
# 任务每次只运行几百毫秒就退出；引擎本身跟随 WPS 存活，WPS 全关后按 idle 退出。
#
#   register / unregister / status
[CmdletBinding()]
param([ValidateSet('register', 'unregister', 'status')][string]$Action = 'register')
$ErrorActionPreference = 'Stop'

$TaskName = 'WPSPDF-EngineOnDemand'
$Root = Split-Path -Parent $PSScriptRoot
$Py = (Get-Command py -ErrorAction SilentlyContinue)
if (-not $Py) { throw "找不到 py 启动器" }
$Script = Join-Path $Root 'tools\watch_once.py'

switch ($Action) {
    'register' {
        $taskAct = New-ScheduledTaskAction -Execute $Py.Source `
            -Argument "-3 `"$Script`"" -WorkingDirectory $Root
        $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
            -RepetitionInterval (New-TimeSpan -Minutes 1)
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew
        Register-ScheduledTask -TaskName $TaskName -Action $taskAct -Trigger $trigger `
            -Settings $settings -Description 'WPSPDF：WPS 在跑且引擎未启动时按需拉起引擎' -Force | Out-Null
        Write-Host "  · 已注册计划任务 $TaskName（每 1 分钟，仅检查，不常驻）" -ForegroundColor Cyan
    }
    'unregister' {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "  · 已移除计划任务 $TaskName" -ForegroundColor Cyan
    }
    default {
        Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue |
            Select-Object TaskName, State | Format-Table -AutoSize | Out-String -Width 80
        Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue |
            Select-Object LastRunTime, LastTaskResult, NextRunTime | Format-List
    }
}
