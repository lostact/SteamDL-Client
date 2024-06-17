import cx_Freeze

build_exe_options = {
    "build_exe": "freeze",
    "include_files": "assets",
    "excludes": ["tkinter", "PyQt5"],
}
cx_Freeze.setup(
    name = "SteamDL",
    version = "1.0.8",
    options = {"build_exe": build_exe_options},
    executables = [cx_Freeze.Executable("main.py",target_name="SteamDL", icon="steamdl.ico",uac_admin=True, base = "gui")]
) 