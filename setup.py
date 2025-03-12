from cx_Freeze import setup, Executable

VERSION = "2.2.3"

build_exe_options = {
    "build_exe": "dist/steamdl",
    "include_files": ["assets", "MicrosoftEdgeWebview2Setup.exe"],
    "excludes": ["tkinter", "PyQt5", "webview.platforms.android", "webview.platforms.cocoa", "mitmproxy.addons.proxyauth","mitmproxy.tools.web","setuptools"],
    "includes": ["mitmproxy_windows"],
    "include_msvcr": True,
    "replace_paths": [("*", "")]
}

bdist_msi_options = {
    "initial_target_dir": "[ProgramFilesFolder]SteamDL",
    "upgrade_code": "{6D92AF12-4EFC-3241-88B7-84B0C6959C53}",
    "install_icon": "steamdl.ico",
    "summary_data": {"author": "SteamDL.ir"},
    "all_users": True,
    # 34: exe file with directory - 1024: deferred - 192: asynchronous without waiting
    "data": {"CustomAction": [("LaunchApp", 34 + 3072 + 192, "TARGETDIR", "[TARGETDIR]steamdl.exe")], "InstallExecuteSequence": [("LaunchApp", "NOT REMOVE", 6500)]}
}

setup(
    name = "SteamDL",
    version = VERSION,
    url = "https://steamdl.ir",
    options = {"build_exe": build_exe_options, "bdist_msi": bdist_msi_options},
    executables = [Executable("main.py", target_name="SteamDL", icon="steamdl.ico", uac_admin=True, shortcut_name="SteamDL", base="gui")]
)
