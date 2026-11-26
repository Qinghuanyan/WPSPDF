' 静默启动 WPSPDF 引擎（不弹黑窗）
' 由加载项在检测到引擎未运行时调用；也可手工双击
Dim sh, fso, here, script
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
script = fso.GetParentFolderName(here) & "\engine\server.py"
sh.CurrentDirectory = fso.GetParentFolderName(here)
' 用 pyw 避免控制台窗口；-3 指定 Python 3
sh.Run "pyw -3 """ & script & """ 38731", 0, False
