from __future__ import annotations

import atexit
import json
import os
import platform
import shutil
import tempfile
from pathlib import Path
from typing import MutableMapping


def ida_library_name(system: str | None = None) -> str:
    system = system or platform.system()
    if system == "Windows":
        return "idalib.dll"
    if system == "Linux":
        return "libidalib.so"
    if system == "Darwin":
        return "libidalib.dylib"
    raise ValueError(f"Unsupported platform for idalib: {system}")


def validate_ida_home(ida_home: str | Path) -> Path:
    home = Path(ida_home).expanduser().resolve()
    if not home.is_dir():
        raise ValueError(f"IDA home is not a directory: {home}")
    if not (home / "ida.hlp").is_file():
        raise ValueError(f"IDA home does not contain ida.hlp: {home}")
    library = home / ida_library_name()
    if not library.is_file():
        raise ValueError(f"IDA home does not contain {library.name}: {home}")
    return home


def idapro_user_dir(config_root: str | Path, system: str | None = None) -> Path:
    root = Path(config_root)
    system = system or platform.system()
    if system == "Windows":
        return root / "Hex-Rays" / "IDA Pro"
    return root / ".idapro"


def idapro_config_path(config_root: str | Path, system: str | None = None) -> Path:
    return idapro_user_dir(config_root, system) / "ida-config.json"


def write_idapro_config(config_root: str | Path, ida_home: str | Path) -> Path:
    home = validate_ida_home(ida_home)
    config_path = idapro_config_path(config_root)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps({"Paths": {"ida-install-dir": str(home)}}, indent=4),
        encoding="utf-8",
    )
    return config_path


def real_ida_user_dir(system: str | None = None) -> Path | None:
    """User dir of the host IDA installation (licenses, registry, ...)."""
    system = system or platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return None
        return Path(appdata) / "Hex-Rays" / "IDA Pro"
    return Path.home() / ".idapro"


def _copy_ida_user_state(config_root: str | Path, system: str | None = None) -> list[str]:
    """Copy per-user idalib state into an isolated config root.

    idalib resolves licenses and its user registry from the config root we
    point HOME/APPDATA at. A pristine temp root would hide the user's
    ``idapro.hexlic``, making every ``open_database`` hard-exit (status 1)
    inside the worker with no Python traceback. Copy the small set of state
    files idalib needs so worker isolation stays license-transparent.
    """
    state_src = real_ida_user_dir(system)
    if state_src is None or not state_src.is_dir():
        return []
    state_dest = idapro_user_dir(config_root, system)
    state_dest.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    candidates: set[Path] = set()
    for name in ("idapro.hexlic", "ida.reg"):
        candidate = state_src / name
        if candidate.is_file():
            candidates.add(candidate)
    candidates.update(p for p in state_src.glob("*.hexlic") if p.is_file())
    for src in sorted(candidates):
        dest = state_dest / src.name
        if not dest.exists():
            shutil.copy2(src, dest)
            copied.append(src.name)
    return copied


def configure_idalib_environment(
    ida_home: str | Path | None,
    *,
    env: MutableMapping[str, str] | None = None,
    config_root: str | Path | None = None,
    cleanup_temp: bool = True,
) -> Path | None:
    if ida_home is None:
        return None

    home = validate_ida_home(ida_home)
    target_env = env if env is not None else os.environ

    if config_root is None:
        root = Path(tempfile.mkdtemp(prefix="idalib-mcp-ida-config-"))
        if cleanup_temp:
            atexit.register(shutil.rmtree, root, ignore_errors=True)
    else:
        root = Path(config_root).expanduser().resolve()

    write_idapro_config(root, home)
    _copy_ida_user_state(root)

    if platform.system() == "Windows":
        target_env["APPDATA"] = str(root)
        existing_path = target_env.get("PATH", "")
        target_env["PATH"] = str(home) + (os.pathsep + existing_path if existing_path else "")
    else:
        target_env["HOME"] = str(root)

    target_env["IDADIR"] = str(home)
    target_env["IDA_HOME"] = str(home)
    return root


def default_ida_home_from_env(env: MutableMapping[str, str] | None = None) -> Path | None:
    target_env = env if env is not None else os.environ
    value = target_env.get("IDA_HOME") or target_env.get("IDADIR")
    if not value:
        return None
    return Path(value)
