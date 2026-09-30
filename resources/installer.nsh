!macro customInit
  nsExec::Exec 'cmd /c "taskkill /F /IM videocut-engine.exe >nul 2>&1"'

  # 如果目标安装目录已存在 storage 用户数据，在旧版本卸载或覆盖前先行备份至同级临时目录
  ${if} ${FileExists} "$INSTDIR\storage\*.*"
    ClearErrors
    Rename "$INSTDIR\storage" "$INSTDIR_storage_backup"
  ${endIf}
!macroend

!macro customInstall
  # 覆盖安装或更新完毕后，安全恢复 storage 用户数据（项目、素材、数据库）
  ${if} ${FileExists} "$INSTDIR_storage_backup\*.*"
    ${ifNot} ${FileExists} "$INSTDIR\storage\*.*"
      ClearErrors
      Rename "$INSTDIR_storage_backup" "$INSTDIR\storage"
      ${if} ${Errors}
        CreateDirectory "$INSTDIR\storage"
        CopyFiles /SILENT "$INSTDIR_storage_backup\*.*" "$INSTDIR\storage"
        RMDir /r "$INSTDIR_storage_backup"
      ${endIf}
    ${else}
      CopyFiles /SILENT "$INSTDIR_storage_backup\*.*" "$INSTDIR\storage"
      RMDir /r "$INSTDIR_storage_backup"
    ${endIf}
  ${endIf}
  # 授予本地标准用户组对 storage 目录的完整修改写权限，杜绝安装在 C:\Program Files 下时的 UAC 权限拒绝与 SQLite unable to open database file
  CreateDirectory "$INSTDIR\storage"
  nsExec::Exec 'cmd /c "icacls \"$INSTDIR\storage\" /grant *S-1-5-32-545:(OI)(CI)M /T /Q >nul 2>&1"'
!macroend

!macro customUnInit
  nsExec::Exec 'cmd /c "taskkill /F /IM videocut-engine.exe >nul 2>&1"'

  # 卸载启动时：将用户数据移出待清理的 INSTDIR
  ${if} ${FileExists} "$INSTDIR\storage\*.*"
    ClearErrors
    Rename "$INSTDIR\storage" "$INSTDIR_storage_backup"
  ${endIf}
!macroend

!macro customUnInstall
  # 卸载完成后：还原用户 storage 数据，杜绝由于误卸载或重新安装抹除用户素材与工程库
  ${if} ${FileExists} "$INSTDIR_storage_backup\*.*"
    CreateDirectory "$INSTDIR"
    ClearErrors
    Rename "$INSTDIR_storage_backup" "$INSTDIR\storage"
    ${if} ${Errors}
      CopyFiles /SILENT "$INSTDIR_storage_backup\*.*" "$INSTDIR\storage"
      RMDir /r "$INSTDIR_storage_backup"
    ${endIf}
  ${endIf}
!macroend
