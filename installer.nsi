Unicode true
!include "MUI2.nsh"
!include "nsDialogs.nsh"

Name "JustGivenUp!"
OutFile "build\JustGivenUp-Setup-2.3-win64.exe"
InstallDir "$PROGRAMFILES64\JustGivenUp"
RequestExecutionLevel admin

!define VERSION "2.3"
!define PUBLISHER "RaGAEIDOS"

!define MUI_ABORTWARNING
!define MUI_ICON "assets\shield.ico"
!define MUI_UNICON "assets\shield.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
Page custom PageShortcuts PageShortcutsLeave
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\JustGivenUp.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Run JustGivenUp!"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Var CreateDesktopShortcut
Var CreateStartMenuShortcut

Function PageShortcuts
  !insertmacro MUI_HEADER_TEXT "Choose Shortcuts" "Select where to create program shortcuts."
  nsDialogs::Create 1018
  Pop $0

  ${NSD_CreateLabel} 0 0 100% 20u \
    "Create shortcuts for JustGivenUp!:"

  ${NSD_CreateCheckBox} 15u 30u 90% 10u "&Desktop shortcut"
  Pop $CreateDesktopShortcut
  ${NSD_Check} $CreateDesktopShortcut

  ${NSD_CreateCheckBox} 15u 45u 90% 10u "&Start Menu folder"
  Pop $CreateStartMenuShortcut
  ${NSD_Check} $CreateStartMenuShortcut

  nsDialogs::Show
FunctionEnd

Function PageShortcutsLeave
  ${NSD_GetState} $CreateDesktopShortcut $CreateDesktopShortcut
  ${NSD_GetState} $CreateStartMenuShortcut $CreateStartMenuShortcut
FunctionEnd

Section "Install" SecInstall
  SetOutPath "$INSTDIR"

  ; NOTE: User data in %APPDATA%\JustGivenUp\ is NEVER deleted.
  ; config.json, guardian.log, and stats are preserved across upgrades.

  File "build\JustGivenUp.exe"
  File "build\JustGivenUpSvc.exe"
  File "build\JustGivenUp_watchdog.exe"
  File "build\320n.onnx"
  File "build\config.json"
  File "assets\shield.ico"
  File /r "build\*.dll"

  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" \
    "JustGivenUp" "$INSTDIR\JustGivenUp.exe"

  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\JustGivenUp" \
    "DisplayName" "JustGivenUp! - Screen Guardian"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\JustGivenUp" \
    "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\JustGivenUp" \
    "DisplayIcon" "$INSTDIR\shield.ico"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\JustGivenUp" \
    "Publisher" "${PUBLISHER}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\JustGivenUp" \
    "DisplayVersion" "${VERSION}"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\JustGivenUp" \
    "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\JustGivenUp" \
    "NoRepair" 1

  ${If} $CreateStartMenuShortcut != 0
    CreateDirectory "$SMPROGRAMS\JustGivenUp"
    CreateShortCut "$SMPROGRAMS\JustGivenUp\JustGivenUp!.lnk" \
      "$INSTDIR\JustGivenUp.exe" "" "$INSTDIR\shield.ico"
    CreateShortCut "$SMPROGRAMS\JustGivenUp\Uninstall JustGivenUp!.lnk" \
      "$INSTDIR\uninstall.exe" "" "$INSTDIR\shield.ico"
  ${EndIf}

  ${If} $CreateDesktopShortcut != 0
    CreateShortCut "$DESKTOP\JustGivenUp!.lnk" \
      "$INSTDIR\JustGivenUp.exe" "" "$INSTDIR\shield.ico"
  ${EndIf}

  nsExec::Exec '"$INSTDIR\JustGivenUpSvc.exe"'

  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
  nsExec::Exec '"$INSTDIR\JustGivenUpSvc.exe"'
  nsExec::Exec 'taskkill.exe /f /im JustGivenUp.exe'
  nsExec::Exec 'taskkill.exe /f /im JustGivenUp_watchdog.exe'

  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Run"
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "JustGivenUp"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\JustGivenUp"

  Delete "$SMPROGRAMS\JustGivenUp\JustGivenUp!.lnk"
  Delete "$SMPROGRAMS\JustGivenUp\Uninstall JustGivenUp!.lnk"
  RMDir "$SMPROGRAMS\JustGivenUp"
  Delete "$DESKTOP\JustGivenUp!.lnk"

  RMDir /r "$INSTDIR"
SectionEnd

