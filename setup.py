from cx_Freeze import setup, Executable

build_exe_options = {
    "build_exe": "dist/steamdl",
    "include_files": ["assets","preferences.json"],
    "excludes": ["tkinter", "PyQt5", "webview.platforms.android", "webview.platforms.cocoa", "mitmproxy.addons.proxyauth"],
    "includes": ["mitmproxy_windows"],
    "replace_paths": [("*", "")]
}

setup(
    name = "SteamDL",
    version = "2.0.1",
    options = {"build_exe": build_exe_options},
    executables = [Executable("main.py",target_name="SteamDL", icon="steamdl.ico",uac_admin=True, base = "gui"),
    ]
)
