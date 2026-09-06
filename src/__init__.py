import os

from src.game_path import (
    get_game_exe_config_value,
    get_launcher_exe_config_value,
)


def _ensure_system32_in_path() -> None:
    system32 = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "System32")
    path_value = os.environ.get("PATH", "")
    entries = [entry for entry in path_value.split(os.pathsep) if entry]
    norm_system32 = os.path.normcase(os.path.normpath(system32))
    has_system32 = any(
        os.path.normcase(os.path.normpath(entry)) == norm_system32 for entry in entries
    )
    if os.path.isdir(system32) and not has_system32:
        os.environ["PATH"] = path_value + (os.pathsep if path_value else "") + system32


_ensure_system32_in_path()

GAME_NAME = "BD2"
GAME_EXE = get_game_exe_config_value()
LAUNCHER_EXE = get_launcher_exe_config_value()
HWND_CLASS = os.environ.get("OK_BD2_HWND_CLASS", "UnityWndClass")
