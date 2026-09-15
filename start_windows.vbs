' VideoCut Windows 一键免终端启动脚本
' 通过 WScript.Shell 的 0 参数隐藏运行窗口，彻底规避控制台黑框弹出

Set WshShell = CreateObject("WScript.Shell")
strCurDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' 优先检测本地虚拟环境的 pythonw.exe，未找到则使用全局 pythonw
Dim pythonwPath
If CreateObject("Scripting.FileSystemObject").FileExists(strCurDir & "\.venv\Scripts\pythonw.exe") Then
    pythonwPath = """" & strCurDir & "\.venv\Scripts\pythonw.exe"""
Else
    pythonwPath = "pythonw"
End If

WshShell.CurrentDirectory = strCurDir
WshShell.Run pythonwPath & " launcher.py", 0, False
