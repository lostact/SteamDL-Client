import cx_Freeze

build_exe_options = {
    "build_exe": "dist/steamdl",
    "include_files": "assets",
    "excludes": ["tkinter", "PyQt5", "webview.platforms.android", "webview.platforms.cocoa"],
    "replace_paths": [("*", "")]
}

cx_Freeze.setup(
    name = "SteamDL",
    version = "1.1.3",
    options = {"build_exe": build_exe_options},
    executables = [cx_Freeze.Executable("main.py",target_name="SteamDL", icon="steamdl.ico",uac_admin=True, base = "gui")]
)
