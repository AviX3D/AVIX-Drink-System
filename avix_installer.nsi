; AVIX Drink System — NSIS Installer Script
; Genere un installeur Windows professionnel

!define APP_NAME "AVIX Drink System"
!define APP_VERSION "3.0.0"
!define APP_PUBLISHER "AVIX_3D"
!define APP_URL "https://avix3d.com"
!define EXE_NAME "AVIX Drink System.exe"
!define INSTALL_DIR "$PROGRAMFILES\AVIX3D\Drink System"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "AVIX_Drink_System_Setup.exe"
InstallDir "${INSTALL_DIR}"
InstallDirRegKey HKLM "Software\AVIX3D\DrinkSystem" "Install_Dir"
RequestExecutionLevel admin
SetCompressor lzma

; Pages
Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "AVIX Drink System (requis)"
  SectionIn RO
  SetOutPath "$INSTDIR"
  File "dist\AVIX Drink System.exe"

  ; Raccourci bureau
  CreateShortcut "$DESKTOP\AVIX Drink System.lnk" "$INSTDIR\${EXE_NAME}"

  ; Raccourci menu demarrer
  CreateDirectory "$SMPROGRAMS\AVIX3D"
  CreateShortcut "$SMPROGRAMS\AVIX3D\AVIX Drink System.lnk" "$INSTDIR\${EXE_NAME}"

  ; Registry pour desinstallation
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AVIXDrinkSystem" \
    "DisplayName" "${APP_NAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AVIXDrinkSystem" \
    "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AVIXDrinkSystem" \
    "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AVIXDrinkSystem" \
    "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AVIXDrinkSystem" \
    "URLInfoAbout" "${APP_URL}"

  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\${EXE_NAME}"
  Delete "$INSTDIR\uninstall.exe"
  RMDir "$INSTDIR"
  Delete "$DESKTOP\AVIX Drink System.lnk"
  Delete "$SMPROGRAMS\AVIX3D\AVIX Drink System.lnk"
  RMDir "$SMPROGRAMS\AVIX3D"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AVIXDrinkSystem"
SectionEnd
