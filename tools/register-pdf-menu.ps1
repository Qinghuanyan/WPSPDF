# 注册/取消「PDF 转表格」右键菜单（HKCU，仅当前用户，不写 HKLM）
#   register / unregister / status
[CmdletBinding()]
param([ValidateSet('register', 'unregister', 'status')][string]$Action = 'status')
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$key = 'HKCU:\Software\Classes\SystemFileAssociations\.pdf\shell\WPSPDF'
$bat = Join-Path $Root 'tools\open-with-wpspdf.bat'
# 右键菜单图标必须是 .ico（PNG 会被 Windows 显示成通用文档图标）
$icon = Join-Path $Root 'addon-pdf\images\wpspdf.ico'
# 形式取 "路径,序号" 且路径不加引号（本项目路径无空格）——这是 Windows 最兼容的写法
$iconValue = if (Test-Path $icon) { "$icon,0" } else { Join-Path $Root 'addon-pdf\images\convert.png' }

switch ($Action) {
    'register' {
        New-Item -Path $key -Force | Out-Null
        Set-ItemProperty -Path $key -Name '(default)' -Value 'PDF 转表格（WPSPDF）'
        Set-ItemProperty -Path $key -Name 'Icon' -Value $iconValue
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
