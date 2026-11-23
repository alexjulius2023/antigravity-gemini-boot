' Silent Windows Launcher for Antigravity x Gemini Catgirl Boot Animation
' Runs pythonw.exe without popping up any console window, forwarding CLI arguments.
Option Explicit

Dim fso, shell, scriptDir, pythonw, launcherPy, args, i, cmd, pyDir, folder
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
launcherPy = scriptDir & "\launcher.py"

pythonw = "pythonw.exe"
pyDir = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python")
If fso.FolderExists(pyDir) Then
    For Each folder In fso.GetFolder(pyDir).SubFolders
        If fso.FileExists(folder.Path & "\pythonw.exe") Then
            pythonw = folder.Path & "\pythonw.exe"
        End If
    Next
End If

args = ""
For i = 0 To WScript.Arguments.Count - 1
    args = args & " """ & WScript.Arguments(i) & """"
Next

cmd = """" & pythonw & """ """ & launcherPy & """" & args
shell.Run cmd, 0, False
