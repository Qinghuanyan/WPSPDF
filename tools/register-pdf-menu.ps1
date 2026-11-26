# 注册/取消「PDF 转表格」右键菜单（HKCU，仅当前用户，不写 HKLM）
#   register / unregister / status
[CmdletBinding()]
param([ValidateSet('register', 'unregister', 'status')][string]$Action = 'status')
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$key = 'HKCU:\Software\Classes\SystemFileAssociations\.pdf\shell\WPSPDF'
$bat = Join-Path $Root 'tools\open-with-wpspdf.bat'
$icon = Join-Path $Root 'addon-pdf\images\convert.png'

switch ($Action) {
    'register' {
        New-Item -Path $key -Force | Out-Null
        Set-ItemProperty -Path $key -Name '(default)' -Value 'PDF 转表格（WPSPDF）'
        Set-ItemProperty -Path $key -Name 'Icon' -Value $icon
        New-Item -Path "$key\command" -Force | Out-Null
        Set-ItemProperty -Path "$key\command" -Name '(default)' -Value "`"$bat`" `"%1`""
        Write-Host "  · 已注册右键菜单：$key" -ForegroundColor Cyan
    }
    'unregister' {
        if (Test-Path $key) { Remove-Item -Path $key -Recurse -Force; Write-Host "  · 已移除右键菜单" -ForegroundColor Cyan }
        else { Write-Host "  · 未注册，跳过" -ForegroundColor DarkGray }
    }
    default {
        if (Test-Path $key) {
            Write-Host "  · 已注册" -ForegroundColor Green
            Get-ItemProperty -Path $key | Format-List
            Get-ItemProperty -Path "$key\command" | Select-Object -ExpandProperty '(default)'
        } else {
            Write-Host "  · 未注册" -ForegroundColor Yellow
        }
    }
}
