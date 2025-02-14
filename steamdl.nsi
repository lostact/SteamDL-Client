!define APPNAME "SteamDL"
!define COMPANYNAME "SteamDL.ir"
!define DESCRIPTION "SteamDL App"

!define VERSIONMAJOR 2
!define VERSIONMINOR 0
!define VERSIONBUILD 3

!define HELPURL "https://steamdl.ir/contact-us/"
!define UPDATEURL "https://steamdl.ir/"
!define ABOUTURL "https://steamdl.ir/about-us"

!define INSTALLSIZE 86000

RequestExecutionLevel admin

InstallDir "$PROGRAMFILES\${APPNAME}"

Name "${APPNAME}"
Icon "steamdl.ico"
outFile "dist\steamdl_installer.exe"

!include LogicLib.nsh

#page license
page directory
Page instfiles

!macro VerifyUserIsAdmin
UserInfo::GetAccountType
pop $0
${If} $0 != "admin"
	messageBox mb_iconstop "Administrator rights required!"
	setErrorLevel 740
	quit
${EndIf}
!macroend

function .onInit
	ExecWait "taskKill /IM steamdl.exe /F"
	setShellVarContext all
	!insertmacro VerifyUserIsAdmin
functionEnd

section "install"
	setOutPath $INSTDIR
	IfFileExists $INSTDIR\uninstall.exe +1 NotInstalled
		Rename $INSTDIR\account.txt $PLUGINSDIR\account.txt
		Rename $INSTDIR\rx.txt $PLUGINSDIR\rx.txt
		RMDir /R $INSTDIR
		CreateDirectory $INSTDIR
		Rename $PLUGINSDIR\account.txt $INSTDIR\account.txt
		Rename $PLUGINSDIR\rx.txt $INSTDIR\rx.txt
	NotInstalled:
	
	
	File /r "dist\steamdl\"
	File "steamdl.ico"

	writeUninstaller "$INSTDIR\uninstall.exe"

	# Start Menu
	createDirectory "$SMPROGRAMS\${APPNAME}"
	createShortCut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\steamdl.exe" "" "$INSTDIR\steamdl.ico"
	SetShellVarContext current
	createShortCut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\steamdl.exe" "" "$INSTDIR\steamdl.ico"

	# Registry information for add/remove programs
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "DisplayName" "${APPNAME}"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "UninstallString" "$\"$INSTDIR\uninstall.exe$\""
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "QuietUninstallString" "$\"$INSTDIR\uninstall.exe$\" /S"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "InstallLocation" "$\"$INSTDIR$\""
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "DisplayIcon" "$\"$INSTDIR\steamdl.ico$\""
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "Publisher" "$\"${COMPANYNAME}$\""
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "HelpLink" "$\"${HELPURL}$\""
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "URLUpdateInfo" "$\"${UPDATEURL}$\""
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "URLInfoAbout" "$\"${ABOUTURL}$\""
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "DisplayVersion" "${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}"
	WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "VersionMajor" ${VERSIONMAJOR}
	WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "VersionMinor" ${VERSIONMINOR}
	WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "NoModify" 1
	WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "NoRepair" 1
	WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "EstimatedSize" ${INSTALLSIZE}

	IfSilent +15
	ReadRegStr $0 HKLM "SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" "pv"

	${If} $0 == ""
		SetDetailsPrint both
		DetailPrint "$0"
		DetailPrint "Installing: WebView2 Runtime"
		SetDetailsPrint listonly
		InitPluginsDir
		CreateDirectory "$pluginsdir\webview2bootstrapper"
		SetOutPath "$pluginsdir\webview2bootstrapper"
		File "MicrosoftEdgeWebview2Setup.exe"
		ExecWait '"$pluginsdir\webview2bootstrapper\MicrosoftEdgeWebview2Setup.exe"'
		SetDetailsPrint both
	${EndIf}

	setOutPath $INSTDIR
	CopyFiles $INSTDIR\*.dll $INSTDIR\assets\_internal
	Exec "steamdl.exe"
sectionEnd

# Uninstaller
function un.onInit
	SetShellVarContext all
	ExecWait "taskKill /IM steamdl.exe /F /T"

	MessageBox MB_OKCANCEL "Permanantly remove ${APPNAME}?" IDOK next
		Abort
	next:
		!insertmacro VerifyUserIsAdmin
functionEnd

section "uninstall"
	delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
	rmDir "$SMPROGRAMS\${APPNAME}"

	SetShellVarContext current
	delete "$DESKTOP\${APPNAME}.lnk"

	rmDir /r $INSTDIR

	DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}"
sectionEnd