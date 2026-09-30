!macro customInit
  nsExec::Exec 'cmd /c "taskkill /F /IM VideoCut.exe /IM videocut-engine.exe >nul 2>&1"'

  # 1. 尝试从注册表与常见路径探测已有旧版本的安装目录
  Var /GLOBAL OLD_INSTALL_DIR
  StrCpy $OLD_INSTALL_DIR ""

  ReadRegStr $0 HKCU "Software\videocut" "InstallLocation"
  ${if} $0 != ""
    StrCpy $OLD_INSTALL_DIR $0
  ${else}
    ReadRegStr $0 HKLM "Software\videocut" "InstallLocation"
    ${if} $0 != ""
      StrCpy $OLD_INSTALL_DIR $0
    ${else}
      ReadRegStr $0 HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\9caeb144-b16d-5ef3-8672-3b3da28c53f2" "InstallLocation"
      ${if} $0 != ""
        StrCpy $OLD_INSTALL_DIR $0
      ${else}
        # 尝试从常见路径探测历史数据库
        ${if} ${FileExists} "$LOCALAPPDATA\Programs\videocut\storage\videocut.db"
          StrCpy $OLD_INSTALL_DIR "$LOCALAPPDATA\Programs\videocut"
        ${elseIf} ${FileExists} "D:\Program Files (x86)\VideoCut\storage\videocut.db"
          StrCpy $OLD_INSTALL_DIR "D:\Program Files (x86)\VideoCut"
        ${elseIf} ${FileExists} "C:\Program Files\VideoCut\storage\videocut.db"
          StrCpy $OLD_INSTALL_DIR "C:\Program Files\VideoCut"
        ${endIf}
      ${endIf}
    ${endIf}
  ${endIf}

  # 2. 如果旧安装目录下存在 storage 用户数据，在覆盖安装或旧版卸载前将其完整安全备份至 LOCALAPPDATA 独立持久区
  ${if} $OLD_INSTALL_DIR != ""
    ${if} ${FileExists} "$OLD_INSTALL_DIR\storage\videocut.db"
      CreateDirectory "$LOCALAPPDATA\videocut_persistent_storage"
      nsExec::Exec 'cmd /c "xcopy \"$OLD_INSTALL_DIR\storage\" \"$LOCALAPPDATA\videocut_persistent_storage\" /E /I /Y /Q /H /R >nul 2>&1"'
    ${endIf}
  ${endIf}
!macroend

!macro customInstall
  # 1. 显式记录当前安装路径到注册表，确保未来每次更新均可精准识别旧目录
  WriteRegStr HKCU "Software\videocut" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\9caeb144-b16d-5ef3-8672-3b3da28c53f2" "InstallLocation" "$INSTDIR"

  # 2. 覆盖安装或更新完毕后，安全恢复 storage 用户数据（项目、素材、数据库、输出成片）
  ${if} ${FileExists} "$LOCALAPPDATA\videocut_persistent_storage\videocut.db"
    CreateDirectory "$INSTDIR\storage"
    nsExec::Exec 'cmd /c "xcopy \"$LOCALAPPDATA\videocut_persistent_storage\" \"$INSTDIR\storage\" /E /I /Y /Q /H /R >nul 2>&1"'
  ${endIf}

  # 3. 授予本地标准用户组对 storage 目录的完整修改写权限，杜绝安装在 Program Files 时的 UAC 权限拒绝与 SQLite unable to open database file
  CreateDirectory "$INSTDIR\storage"
  nsExec::Exec 'cmd /c "icacls \"$INSTDIR\storage\" /grant *S-1-5-32-545:(OI)(CI)M /T /Q >nul 2>&1"'
!macroend

!macro customUnInit
  nsExec::Exec 'cmd /c "taskkill /F /IM VideoCut.exe /IM videocut-engine.exe >nul 2>&1"'

  # 卸载启动时：始终无条件将现有 storage 数据镜像同步到 LOCALAPPDATA 独立持久区，防范更新卸载流程抹除数据
  ${if} ${FileExists} "$INSTDIR\storage\videocut.db"
    CreateDirectory "$LOCALAPPDATA\videocut_persistent_storage"
    nsExec::Exec 'cmd /c "xcopy \"$INSTDIR\storage\" \"$LOCALAPPDATA\videocut_persistent_storage\" /E /I /Y /Q /H /R >nul 2>&1"'
  ${endIf}
!macroend

!macro customUnInstall
  # 卸载完成后：保留 LOCALAPPDATA 独立持久区中的备份，以便用户重新安装时一键恢复所有工程与素材
!macroend
