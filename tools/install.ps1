<#
  WPSPDF 加载项安装脚本（可回退）
  作用范围（仅此三处，绝不动 WPS 安装目录）：
    %APPDATA%\kingsoft\wps\jsaddons\WPSPDF_1.0.0\     新增目录
    %APPDATA%\kingsoft\wps\jsaddons\publish.xml        新增或合并条目
    %APPDATA%\kingsoft\wps\jsaddons\.wpspdf-installed  标记文件（供卸载判断）
  回退：tools\uninstall.ps1
#>
[CmdletBinding()]
param(
    [string]$AddonName = 'WPSPDF',
    [string]$Version = '1.0.0'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$AddonSrc    = Join-Path $ProjectRoot 'addon'
$AddonsRoot  = Join-Path $env:APPDATA 'kingsoft\wps\jsaddons'
$TargetDir   = Join-Path $AddonsRoot ("{0}_{1}" -f $AddonName, $Version)
$PublishXml  = Join-Path $AddonsRoot 'publish.xml'
$Marker      = Join-Path $AddonsRoot '.wpspdf-installed'
$EvidenceDir = Join-Path $ProjectRoot 'evidence'

function Write-Step($msg) { Write-Host "  · $msg" -ForegroundColor Cyan }

if (-not (Test-Path $AddonSrc)) { throw "找不到加载项源目录: $AddonSrc" }
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

# ── 1. 记录安装前状态 ─────────────────────────────────────────
$ts = Get-Date -Format 'yyyyMMdd-HHmmss'
$pre = [ordered]@{
    timestamp        = (Get-Date).ToString('s')
    jsaddons_existed = (Test-Path $AddonsRoot)
    publish_xml      = (Test-Path $PublishXml)
    target_existed   = (Test-Path $TargetDir)
}
$pre | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $EvidenceDir "install-pre-$ts.json")
Write-Host "== WPSPDF 加载项安装 ==" -ForegroundColor Green
Write-Step ("安装前: jsaddons存在={0} publish.xml存在={1}" -f $pre.jsaddons_existed, $pre.publish_xml)

# ── 2. 备份既有 publish.xml ───────────────────────────────────
if (Test-Path $PublishXml) {
    Copy-Item $PublishXml (Join-Path $EvidenceDir "publish.xml.bak-$ts") -Force
    Write-Step "已备份 publish.xml → evidence\publish.xml.bak-$ts"
}

# ── 3. 拷贝加载项 ─────────────────────────────────────────────
New-Item -ItemType Directory -Force -Path $AddonsRoot | Out-Null
if (Test-Path $TargetDir) { Remove-Item $TargetDir -Recurse -Force }
Copy-Item $AddonSrc $TargetDir -Recurse -Force
Write-Step "已拷贝 → $TargetDir"

# ── 4. 写入 / 合并 publish.xml ────────────────────────────────
$entry = @"
  <jsplugin name="$AddonName" type="et" url="${AddonName}_${Version}" version="$Version" enable="enable_dev" install="null" customDomain=""/>
"@
if (Test-Path $PublishXml) {
    [xml]$doc = Get-Content $PublishXml -Raw -Encoding UTF8
    $root = $doc.DocumentElement
    if ($root.Name -ne 'jsplugins') { throw "publish.xml 根节点不是 <jsplugins>，已中止（原文件已备份）" }
    $existing = @($root.jsplugin | Where-Object { $_.name -eq $AddonName })
    foreach ($n in $existing) { [void]$root.RemoveChild($n) }
    $frag = $doc.CreateDocumentFragment()
    $frag.InnerXml = $entry
    [void]$root.AppendChild($frag)
    $doc.Save($PublishXml)
    Write-Step "已合并条目到既有 publish.xml"
} else {
    $xmlText = "<jsplugins>`n$entry</jsplugins>`n"
    Set-Content -Path $PublishXml -Value $xmlText -Encoding UTF8 -NoNewline
    Write-Step "已创建 $PublishXml"
}

# ── 5. 标记（供卸载判断 jsaddons 是否由本工具创建）───────────
@{
    installed_at = (Get-Date).ToString('s')
    created_dir  = -not $pre.jsaddons_existed
    version      = $Version
} | ConvertTo-Json | Set-Content -Encoding UTF8 $Marker

Write-Host ""
Write-Host "安装完成。" -ForegroundColor Green
Write-Host "  下次启动 WPS 表格(et) 会出现「PDF 工具」选项卡。" -ForegroundColor Yellow
Write-Host "  回退命令: powershell -ExecutionPolicy Bypass -File `"$ProjectRoot\tools\uninstall.ps1`"" -ForegroundColor DarkGray
