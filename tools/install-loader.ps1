# 安装/卸载「轻量加载器」登录自启（参考 LocalReadTranslate 的分层启动结构）
#
# 常驻的只有这个加载器：只导入 Python 标准库，不加载 OCR 模型、空闲 CPU ≈0。
# 重引擎（engine/server.py）仍然完全按需：只有点窗格里的「启动引擎」才会被拉起，
# 空闲 20 秒自行退出 —— 所以「WPS 关了引擎就关」依然成立。
#
#   register / unregister / status / start / stop
[CmdletBinding()]
param([ValidateSet('register', 'unregister', 'status', 'start', 'stop')][string]$Action = 'register')
$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$Loader = Join-Path $Root 'engine\loader.py'
$Startup = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
$Lnk = Join-Path $Startup 'WPSPDF Add-in Loader.lnk'
$Pyw = (Get-Command pyw -ErrorAction SilentlyContinue)

function LoaderUp {
    try { return [bool](Invoke-RestMethod -Uri 'http://127.0.0.1:38730/ping' -TimeoutSec 2).ok } catch { return $false }
}

switch ($Action) {
    'register' {
        if (-not $Pyw) { throw "找不到 pyw（Python 启动器）" }
        if (-not (Test-Path $Loader)) { throw "找不到 $Loader" }
        New-Item -ItemType Directory -Force -Path $Startup | Out-Null
        $sh = New-Object -ComObject WScript.Shell
        $s = $sh.CreateShortcut($Lnk)
        $s.TargetPath = $Pyw.Source
        $s.Arguments = "-3 `"$Loader`""
        $s.WorkingDirectory = $Root
        $s.WindowStyle = 7          # 最小化启动，不弹控制台
        $s.Description = 'WPSPDF 轻量加载器（按需拉起引擎，不加载模型）'
        $s.Save()
        Write-Host "  · 已创建登录自启：$Lnk" -ForegroundColor Cyan
        Start-Process -FilePath $Pyw.Source -ArgumentList "-3 `"$Loader`"" -WorkingDirectory $Root -WindowStyle Hidden
        for ($i=0; $i -lt 20; $i++) { Start-Sleep -Milliseconds 300; if (LoaderUp) { break } }
        Write-Host ("  · 加载器状态：{0}" -f $(if (LoaderUp) { '在线 127.0.0.1:38730' } else { '未就绪' })) -ForegroundColor Yellow
    }
    'unregister' {
        if (Test-Path $Lnk) { Remove-Item $Lnk -Force; Write-Host "  · 已删除登录自启快捷方式" -ForegroundColor Cyan }
        else { Write-Host "  · 没有自启快捷方式" -ForegroundColor DarkGray }
        try { Invoke-RestMethod -Uri 'http://127.0.0.1:38730/shutdown' -Method Post -TimeoutSec 2 | Out-Null } catch {}
        Write-Host "  · 已请求加载器退出" -ForegroundColor Cyan
    }
    'start' {
        Start-Process -FilePath $Pyw.Source -ArgumentList "-3 `"$Loader`"" -WorkingDirectory $Root -WindowStyle Hidden
        for ($i=0; $i -lt 20; $i++) { Start-Sleep -Milliseconds 300; if (LoaderUp) { break } }
        Write-Host ("  · 加载器：{0}" -f $(if (LoaderUp) { '在线' } else { '未就绪' }))
    }
    'stop' {
        try { Invoke-RestMethod -Uri 'http://127.0.0.1:38730/shutdown' -Method Post -TimeoutSec 2 | Out-Null; Write-Host "  · 已请求退出" -ForegroundColor Cyan }
        catch { Write-Host "  · 加载器没在跑" -ForegroundColor DarkGray }
    }
    default {
        $eng = try { (Invoke-RestMethod -Uri 'http://127.0.0.1:38731/ping' -TimeoutSec 1).version } catch { $null }
        [pscustomobject]@{
            LoaderOnline = (LoaderUp)
            AutostartLnk = (Test-Path $Lnk)
            EngineOnline = [bool]$eng
            EngineVersion = $eng
        } | Format-List
    }
}
