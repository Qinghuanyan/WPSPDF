# 安装/卸载「离线本地包」形式的 PDF 加载项（不需要引擎常驻）
#
# 依据 wpsjs 官方离线安装格式（node_modules/wpsjs/src/lib/build.js:163）：
#   %APPDATA%\kingsoft\wps\jsaddons\<Name>_<Version>\   ← 加载项文件
#   publish.xml: <jsplugin name="<Name>" type="pdf" url="<Name>_<Version>" version="<Version>" .../>
# url 是**目录名**而不是网址，所以 WPS 从本地磁盘读 ribbon.xml / 页面，不依赖 http 服务。
#
#   register / unregister / status
[CmdletBinding()]
param([ValidateSet('register', 'unregister', 'status')][string]$Action = 'register')
$ErrorActionPreference = 'Stop'

$Name = 'WPSPDFPdf'
$Version = '1.0.0'
$PkgDirName = "${Name}_${Version}"
$Root = Split-Path -Parent $PSScriptRoot
$Src = Join-Path $Root 'addon-pdf'
$JsAddons = Join-Path $env:APPDATA 'kingsoft\wps\jsaddons'
$PkgDir = Join-Path $JsAddons $PkgDirName
$PubXml = Join-Path $JsAddons 'publish.xml'

function Read-Entries {
    if (-not (Test-Path $PubXml)) { return @() }
    [xml]$x = Get-Content $PubXml -Raw -Encoding UTF8
    if (-not $x.jsplugins) { return @() }
    $list = @()
    foreach ($n in $x.jsplugins.ChildNodes) {
        if ($n.NodeType -eq 'Element') { $list += $n }
    }
    return $list
}

function Write-Entries($entries) {
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append('<jsplugins>')
    foreach ($e in $entries) {
        # 必须用 LocalName：XmlElement 的 .Name 在 PowerShell 里会被同名属性覆盖
        [void]$sb.Append('  <' + $e.LocalName)
        foreach ($a in $e.Attributes) { [void]$sb.Append(" $($a.Name)=`"$($a.Value)`"") }
        [void]$sb.Append(' />')
    }
    [void]$sb.Append('</jsplugins>')
    Set-Content -Path $PubXml -Value $sb.ToString() -Encoding UTF8 -NoNewline
}

switch ($Action) {
    'register' {
        if (-not (Test-Path $Src)) { throw "源目录不存在：$Src" }
        New-Item -ItemType Directory -Force -Path $JsAddons | Out-Null
        if (Test-Path $PkgDir) { Remove-Item -Recurse -Force $PkgDir }
        Copy-Item -Recurse -Force $Src $PkgDir

        # 清掉同名/同 url 的旧条目，避免一个页签两份注册
        $entries = @(Read-Entries | Where-Object { $_.name -ne $Name -and $_.url -ne $PkgDirName })
        $xml = '<jsplugin name="{0}" type="pdf" url="{1}" version="{2}" enable="enable_dev" install="null" customDomain="" />' -f $Name, $PkgDirName, $Version
        $new = New-Object System.Xml.XmlDocument
        $new.LoadXml($xml)
        $entries += $new.DocumentElement
        Write-Entries $entries

        Write-Host "  · 已安装离线包：$PkgDir" -ForegroundColor Cyan
        Write-Host "  · publish.xml 已登记 url=$PkgDirName（本地目录名，不需要引擎）" -ForegroundColor Cyan
        Write-Host "  · 生效条件：完全退出 WPS 再打开 PDF" -ForegroundColor Yellow
    }
    'unregister' {
        if (Test-Path $PkgDir) { Remove-Item -Recurse -Force $PkgDir }
        $entries = @(Read-Entries | Where-Object { $_.name -ne $Name -and $_.url -ne $PkgDirName })
        if (Test-Path $PubXml) { Write-Entries $entries }
        Write-Host "  · 已移除离线包与 publish.xml 条目" -ForegroundColor Cyan
    }
    default {
        $found = @(Read-Entries | Where-Object { $_.name -eq $Name })
        Write-Host ("  · 目录: {0}  存在={1}" -f $PkgDir, (Test-Path $PkgDir))
        Write-Host ("  · publish.xml 条目: {0} 个" -f $found.Count)
        $found | ForEach-Object { $_.OuterXml }
    }
}
