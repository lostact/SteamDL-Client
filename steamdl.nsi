!define APPNAME "SteamDL"
!define COMPANYNAME "SteamDL.ir"
!define DESCRIPTION "SteamDL App"

!define VERSIONMAJOR 2
!define VERSIONMINOR 1
!define VERSIONBUILD 0

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

	IfSilent run_steamdl

	; If the WebView2 folder exists, jump to run_steamdl
	IfFileExists "$PROGRAMFILES32\Microsoft\EdgeWebView\Application" run_steamdl install_webview

	; Otherwise, install WebView2 Runtime
	install_webview:
		SetDetailsPrint both
		DetailPrint "Installing: WebView2 Runtime"
		SetDetailsPrint listonly
		InitPluginsDir
		CreateDirectory "$pluginsdir\webview2bootstrapper"
		SetOutPath "$pluginsdir\webview2bootstrapper"
		File "MicrosoftEdgeWebview2Setup.exe"
		ExecWait '"$pluginsdir\webview2bootstrapper\MicrosoftEdgeWebview2Setup.exe"'
		SetDetailsPrint both
		Goto run_steamdl

	run_steamdl:
		SetOutPath $INSTDIR
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