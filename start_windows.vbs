' VideoCut Windows 一键免终端启动脚本
On Error Resume Next

Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")
strCurDir = fso.GetParentFolderName(WScript.ScriptFullName)

WshShell.CurrentDirectory = strCurDir

Dim pythonExe, launcherPath
launcherPath = """" & strCurDir & "\launcher.py"""

If fso.FileExists(strCurDir & "\.venv\Scripts\pythonw.exe") Then
    pythonExe = """" & strCurDir & "\.venv\Scripts\pythonw.exe"""
ElseIf fso.FileExists(strCurDir & "\.venv\Scripts\python.exe") Then
    pythonExe = """" & strCurDir & "\.venv\Scripts\python.exe"""
Else
    pythonExe = "pythonw"
End If

intReturn = WshShell.Run(pythonExe & " " & launcherPath, 0, False)

If Err.Number <> 0 Then
    MsgBox "启动失败: " & Err.Description & vbCrLf & "请尝试双击运行 [启动软件.bat]", 16, "VideoCut 启动错误"
End If
