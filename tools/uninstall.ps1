<#
  WPSPDF 加载项卸载脚本（完整回退）
  只删除本工具创建的东西：
    jsaddons\WPSPDF_1.0.0\
    jsaddons\publish.xml 中的 WPSPDF 条目（若因此变空则删文件）
    jsaddons\.wpspdf-installed
    jsaddons\（仅当它是本工具创建且已空）
#>
[CmdletBinding()]
param(
    [string]$AddonName = 'WPSPDF',
    [string]$Version = '1.0.0'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$AddonsRoot  = Join-Path $env:APPDATA 'kingsoft\wps\jsaddons'
$TargetDir   = Join-Path $AddonsRoot ("{0}_{1}" -f $AddonName, $Version)
$PublishXml  = Join-Path $AddonsRoot 'publish.xml'
$Marker      = Join-Path $AddonsRoot '.wpspdf-installed'

function Write-Step($msg) { Write-Host "  · $msg" -ForegroundColor Cyan }

Write-Host "== WPSPDF 加载项卸载 ==" -ForegroundColor Green

# 安全断言：目标必须在 jsaddons 之下，且名字带前缀
if ($TargetDir -notlike "$AddonsRoot\*") { throw "路径越界，已中止: $TargetDir" }
if ((Split-Path $TargetDir -Leaf) -notlike "$AddonName`_*") { throw "目录名不匹配，已中止: $TargetDir" }

# ── 1. 删除加载项目录 ─────────────────────────────────────────
if (Test-Path $TargetDir) {
    Remove-Item $TargetDir -Recurse -Force
    Write-Step "已删除 $TargetDir"
} else {
    Write-Step "目录不存在，跳过: $TargetDir"
}

# ── 2. 清理 publish.xml 中的条目 ───────────────────────────────
$createdByUs = $false
if (Test-Path $Marker) {
    try { $createdByUs = (Get-Content $Marker -Raw -Encoding UTF8 | ConvertFrom-Json).created_dir } catch {}
}

if (Test-Path $PublishXml) {
    try {
        [xml]$doc = Get-Content $PublishXml -Raw -Encoding UTF8
        $root = $doc.DocumentElement
        $mine = @($root.jsplugin | Where-Object { $_.name -eq $AddonName })
        foreach ($n in $mine) { [void]$root.RemoveChild($n) }
        $remain = @($root.jsplugin | Where-Object { $_ -ne $null })
        if ($remain.Count -eq 0) {
            Remove-Item $PublishXml -Force
            Write-Step "publish.xml 条目已清空 → 删除文件（无条目即无意义）"
        } else {
            $doc.Save($PublishXml)
            Write-Step ("publish.xml 保留，剩余条目 {0} 个" -f $remain.Count)
        }
    } catch {
        Write-Host "  ! publish.xml 解析失败，未改动（请检查备份 evidence\publish.xml.bak-*）" -ForegroundColor Yellow
    }
}

# ── 3. 清理标记与空目录 ───────────────────────────────────────
if (Test-Path $Marker) { Remove-Item $Marker -Force; Write-Step "已删除标记文件" }

if (Test-Path $AddonsRoot) {
    $left = @(Get-ChildItem $AddonsRoot -Force)
    if ($left.Count -eq 0) {
        Remove-Item $AddonsRoot -Force
        Write-Step "jsaddons 目录已空 → 删除（空目录对 WPS 无用途）"
    } else {
        Write-Step ("jsaddons 仍有 {0} 项，保留" -f $left.Count)
    }
}

Write-Host ""
Write-Host "卸载完成。WPS 重启后「PDF 工具」选项卡消失。" -ForegroundColor Green
Write-Host "  当前状态:" -ForegroundColor DarkGray
Write-Host ("    jsaddons 存在: {0}" -f (Test-Path $AddonsRoot)) -ForegroundColor DarkGray
Write-Host ("    publish.xml 存在: {0}" -f (Test-Path $PublishXml)) -ForegroundColor DarkGray
Write-Host ("    加载项目录存在: {0}" -f (Test-Path $TargetDir)) -ForegroundColor DarkGray
