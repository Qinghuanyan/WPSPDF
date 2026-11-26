# 注册/取消开机自启（HKCU Run），让引擎常驻，避免 WPS 每次启动等它
[CmdletBinding()]
param(
    [ValidateSet('register', 'unregister', 'status')]
    [string]$Action = 'status'
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$name = 'WPSPDF-Engine'
$vbs = Join-Path $Root 'tools\engine-silent.vbs'
$cmd = "$env:WINDIR\System32\wscript.exe `"$vbs`""

switch ($Action) {
    'register' {
        New-Item -Path $key -Force | Out-Null
        Set-ItemProperty -Path $key -Name $name -Value $cmd
        Write-Host "  · 已注册开机自启: $cmd" -ForegroundColor Cyan
    }
    'unregister' {
        if (Get-ItemProperty -Path $key -Name $name -ErrorAction SilentlyContinue) {
            Remove-ItemProperty -Path $key -Name $name
            Write-Host "  · 已移除开机自启" -ForegroundColor Cyan
        } else {
            Write-Host "  · 未注册过，跳过" -ForegroundColor DarkGray
        }
    }
    'status' {
        $v = (Get-ItemProperty -Path $key -Name $name -ErrorAction SilentlyContinue).$name
        if ($v) { Write-Host "  · 当前自启: $v" -ForegroundColor Cyan } else { Write-Host "  · 未注册自启" -ForegroundColor DarkGray }
    }
}
