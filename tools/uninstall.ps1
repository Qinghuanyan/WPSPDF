<#
  WPSPDF 卸载脚本（完整回退）
  删除：
    publish.xml 里 WPSPDF* 条目（若因此为空则删文件）
    %APPDATA%\kingsoft\wps\jsaddons\WPSPDF_1.0.0（历史离线形态遗留）
    .wpspdf-installed 标记
    桌面/开始菜单快捷方式
    HKCU Run 自启项
    jsaddons 目录（仅当已空）
  不删：引擎源码、output 产物
#>
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$JsAddons = Join-Path $env:APPDATA 'kingsoft\wps\jsaddons'
$PublishXml = Join-Path $JsAddons 'publish.xml'
$Marker = Join-Path $JsAddons '.wpspdf-installed'

function Step($m) { Write-Host "  · $m" -ForegroundColor Cyan }
Write-Host "== WPSPDF 卸载 ==" -ForegroundColor Green

# 1. 停引擎
try { Invoke-WebRequest 'http://127.0.0.1:38731/shutdown' -UseBasicParsing -TimeoutSec 2 | Out-Null; Step "已请求引擎退出" } catch { Step "引擎未运行" }

# 2. 清理 publish.xml
if (Test-Path $PublishXml) {
    try {
        [xml]$doc = Get-Content $PublishXml -Raw -Encoding UTF8
        $root = $doc.DocumentElement
        $mine = @()
        $mine += @($root.jspluginonline | Where-Object { $_.name -like 'WPSPDF*' })
        $mine += @($root.jsplugin | Where-Object { $_.name -like 'WPSPDF*' })
        foreach ($n in $mine) { [void]$root.RemoveChild($n) }
        $left = @($root.ChildNodes | Where-Object { $_.NodeType -eq 'Element' })
        if ($left.Count -eq 0) {
            Remove-Item $PublishXml -Force
            Step "publish.xml 已无条目 → 删除文件"
        } else {
            $doc.Save($PublishXml)
            Step ("publish.xml 保留，剩余条目 {0} 个" -f $left.Count)
        }
    } catch {
        Write-Host "  ! publish.xml 解析失败，未改动（备份在 evidence\publish.xml.bak-*）" -ForegroundColor Yellow
    }
}

# 3. 历史离线目录
foreach ($d in @(Get-ChildItem $JsAddons -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'WPSPDF_*' })) {
    if ($d.FullName -like "$JsAddons\*") { Remove-Item $d.FullName -Recurse -Force; Step "已删除 $($d.Name)" }
}
if (Test-Path $Marker) { Remove-Item $Marker -Force; Step "已删除标记文件" }

# 4. 快捷方式 + 自启
$wsh = New-Object -ComObject WScript.Shell
foreach ($n in @('PDF转表格·启动引擎', 'PDF转表格·停止引擎')) {
    foreach ($d in @([Environment]::GetFolderPath('Desktop'), (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'))) {
        $p = Join-Path $d ($n + '.lnk')
        if (Test-Path $p) { Remove-Item $p -Force; Step "已删除快捷方式 $n" }
    }
}
& (Join-Path $PSScriptRoot 'autostart.ps1') -Action unregister

# 5. 空目录
if (Test-Path $JsAddons) {
    $left = @(Get-ChildItem $JsAddons -Force)
    if ($left.Count -eq 0) { Remove-Item $JsAddons -Force; Step "jsaddons 已空 → 删除" }
    else { Step ("jsaddons 仍有 {0} 项，保留" -f $left.Count) }
}

Write-Host ""
Write-Host "卸载完成。WPS 重启后页签消失。" -ForegroundColor Green
Write-Host ("  jsaddons: {0}   publish.xml: {1}" -f (Test-Path $JsAddons), (Test-Path $PublishXml)) -ForegroundColor DarkGray
