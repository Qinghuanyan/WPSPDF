<#
  WPSPDF 安装脚本（可回退）
  改动范围：
    %APPDATA%\kingsoft\wps\jsaddons\publish.xml        两条 jspluginonline 条目（et + pdf）
    %APPDATA%\kingsoft\wps\jsaddons\.wpspdf-installed  标记
    桌面 / 开始菜单 两个快捷方式（启动引擎 / 停止引擎）
    可选：HKCU Run 开机自启（-NoAutostart 可跳过）
  不动 WPS 安装目录、不改用户文件；回退用 tools\uninstall.ps1
#>
[CmdletBinding()]
param(
    [string]$EnginePort = 38731,
    [switch]$NoAutostart
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$JsAddons = Join-Path $env:APPDATA 'kingsoft\wps\jsaddons'
$PublishXml = Join-Path $JsAddons 'publish.xml'
$Marker = Join-Path $JsAddons '.wpspdf-installed'
$Evidence = Join-Path $Root 'evidence'

function Step($m) { Write-Host "  · $m" -ForegroundColor Cyan }

Write-Host "== WPSPDF 安装 ==" -ForegroundColor Green
New-Item -ItemType Directory -Force -Path $Evidence | Out-Null

$ts = Get-Date -Format 'yyyyMMdd-HHmmss'
$pre = [ordered]@{
    timestamp        = (Get-Date).ToString('s')
    jsaddons_existed = (Test-Path $JsAddons)
    publish_xml      = (Test-Path $PublishXml)
}
$pre | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $Evidence "install-pre-$ts.json")
Step ("安装前: jsaddons={0} publish.xml={1}" -f $pre.jsaddons_existed, $pre.publish_xml)

if (Test-Path $PublishXml) {
    Copy-Item $PublishXml (Join-Path $Evidence "publish.xml.bak-$ts") -Force
    Step "已备份 publish.xml"
}

New-Item -ItemType Directory -Force -Path $JsAddons | Out-Null

$entries = @"
  <jspluginonline name="WPSPDF" type="et" url="http://127.0.0.1:$EnginePort/et/" debug="" enable="enable_dev" install="null" customDomain=""/>
  <jspluginonline name="WPSPDFPdf" type="pdf" url="http://127.0.0.1:$EnginePort/pdf/" debug="" enable="enable_dev" install="null" customDomain=""/>
"@

if (Test-Path $PublishXml) {
    [xml]$doc = Get-Content $PublishXml -Raw -Encoding UTF8
    $root = $doc.DocumentElement
    if ($root.Name -ne 'jsplugins') { throw "publish.xml 根节点不是 <jsplugins>，已中止（原文件已备份）" }
    foreach ($n in @($root.jspluginonline)) {
        if ($n.name -like 'WPSPDF*' -or $n.url -like "*:$EnginePort/*") { [void]$root.RemoveChild($n) }
    }
    $frag = $doc.CreateDocumentFragment()
    $frag.InnerXml = $entries
    [void]$root.AppendChild($frag)
    $doc.Save($PublishXml)
    Step "已合并两条条目到既有 publish.xml"
} else {
    Set-Content -Path $PublishXml -Value ("<jsplugins>`n" + $entries + "</jsplugins>`n") -Encoding UTF8 -NoNewline
    Step "已创建 publish.xml（et + pdf 两条）"
}

@{ installed_at = (Get-Date).ToString('s'); engine_port = $EnginePort } |
    ConvertTo-Json | Set-Content -Encoding UTF8 $Marker

Step "创建快捷方式"
& (Join-Path $PSScriptRoot 'make-shortcuts.ps1')

if (-not $NoAutostart) {
    & (Join-Path $PSScriptRoot 'autostart.ps1') -Action register
} else {
    Step "跳过开机自启（-NoAutostart）"
}

$alive = $false
try { Invoke-WebRequest "http://127.0.0.1:$EnginePort/ping" -UseBasicParsing -TimeoutSec 2 | Out-Null; $alive = $true } catch {}
if (-not $alive) {
    Start-Process -FilePath "$env:WINDIR\System32\wscript.exe" -ArgumentList "`"$(Join-Path $Root 'tools\engine-silent.vbs')`"" -WindowStyle Hidden
    Start-Sleep -Seconds 3
    try { Invoke-WebRequest "http://127.0.0.1:$EnginePort/ping" -UseBasicParsing -TimeoutSec 2 | Out-Null; $alive = $true } catch {}
}
Step ("引擎状态: " + $(if ($alive) { "在线 http://127.0.0.1:$EnginePort" } else { "未启动（双击桌面「PDF转表格·启动引擎」）" }))

Write-Host ""
Write-Host "安装完成。重启 WPS 后，PDF 与表格窗口都会出现「PDF转表格」页签。" -ForegroundColor Green
Write-Host "回退: tools\uninstall.ps1" -ForegroundColor DarkGray
