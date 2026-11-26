# 创建「PDF转表格」桌面与开始菜单快捷方式（启动引擎 / 停止引擎）
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$icon = Join-Path $Root 'addon-pdf\images\convert.png'
$wsh = New-Object -ComObject WScript.Shell

$targets = @(
    [pscustomobject]@{ Name = 'PDF转表格·启动引擎'; Args = '';                 Script = (Join-Path $Root 'tools\engine-silent.vbs') },
    [pscustomobject]@{ Name = 'PDF转表格·停止引擎'; Args = '';                 Script = (Join-Path $Root 'tools\stop-engine.bat')  }
)

$dirs = @(
    [Environment]::GetFolderPath('Desktop'),
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs')
)

foreach ($t in $targets) {
    foreach ($d in $dirs) {
        if (-not (Test-Path $d)) { continue }
        $lnkPath = Join-Path $d ($t.Name + '.lnk')
        $lnk = $wsh.CreateShortcut($lnkPath)
        if ($t.Script.ToLower().EndsWith('.vbs')) {
            $lnk.TargetPath = Join-Path $env:WINDIR 'System32\wscript.exe'
            $lnk.Arguments = '"' + $t.Script + '"'
        } else {
            $lnk.TargetPath = Join-Path $env:WINDIR 'System32\cmd.exe'
            $lnk.Arguments = '/c "' + $t.Script + '"'
        }
        $lnk.WorkingDirectory = $Root
        $lnk.Description = 'WPS 内 PDF 转表格（本地引擎）'
        if (Test-Path $icon) { $lnk.IconLocation = $icon }
        $lnk.WindowStyle = 7
        $lnk.Save()
        Write-Host "  · 快捷方式 → $lnkPath" -ForegroundColor Cyan
    }
}
