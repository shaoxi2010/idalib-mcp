from __future__ import annotations

import json
import os
import platform
import tempfile
import unittest
from pathlib import Path

from idalib_mcp.config import (
    configure_idalib_environment,
    ida_library_name,
    idapro_config_path,
    validate_ida_home,
)


class ConfigTests(unittest.TestCase):
    def make_fake_ida_home(self, root: Path) -> Path:
        ida_home = root / "ida"
        ida_home.mkdir()
        (ida_home / "ida.hlp").write_text("", encoding="utf-8")
        (ida_home / ida_library_name()).write_text("", encoding="utf-8")
        return ida_home

    def test_validate_ida_home_accepts_expected_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ida_home = self.make_fake_ida_home(Path(temp_dir))
            self.assertEqual(validate_ida_home(ida_home), ida_home.resolve())

    def test_configure_idalib_environment_writes_process_local_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ida_home = self.make_fake_ida_home(root)
            config_root = root / "config"
            env = {"PATH": "existing"}

            result = configure_idalib_environment(
                ida_home,
                env=env,
                config_root=config_root,
                cleanup_temp=False,
            )

            self.assertEqual(result, config_root.resolve())
            config_path = idapro_config_path(config_root)
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["Paths"]["ida-install-dir"], str(ida_home.resolve()))
            self.assertEqual(env["IDADIR"], str(ida_home.resolve()))
            self.assertEqual(env["IDA_HOME"], str(ida_home.resolve()))
            if platform.system() == "Windows":
                self.assertEqual(env["APPDATA"], str(config_root.resolve()))
                self.assertTrue(env["PATH"].startswith(str(ida_home.resolve()) + os.pathsep))
            else:
                self.assertEqual(env["HOME"], str(config_root.resolve()))


class CopyIdaUserStateTests(unittest.TestCase):
    def test_copies_license_and_registry_into_isolated_root(self) -> None:
        from unittest import mock

        from idalib_mcp.config import _copy_ida_user_state, idapro_user_dir

        with tempfile.TemporaryDirectory() as temp_dir:
            fake_home = Path(temp_dir) / "home"
            src = fake_home / ".idapro"
            src.mkdir(parents=True)
            (src / "idapro.hexlic").write_text("license", encoding="utf-8")
            (src / "extra.hexlic").write_text("license2", encoding="utf-8")
            (src / "ida.reg").write_text("registry", encoding="utf-8")
            (src / "unrelated.txt").write_text("x", encoding="utf-8")

            isolated_root = Path(temp_dir) / "isolated"
            with mock.patch("idalib_mcp.config.Path.home", return_value=fake_home):
                copied = _copy_ida_user_state(isolated_root, system="Linux")

            self.assertEqual(copied, ["extra.hexlic", "ida.reg", "idapro.hexlic"])
            dest = idapro_user_dir(isolated_root, system="Linux")
            self.assertTrue((dest / "idapro.hexlic").is_file())
            self.assertTrue((dest / "ida.reg").is_file())
            self.assertFalse((dest / "unrelated.txt").exists())

    def test_missing_source_user_dir_is_noop(self) -> None:
        from unittest import mock

        from idalib_mcp.config import _copy_ida_user_state

        with tempfile.TemporaryDirectory() as temp_dir:
            fake_home = Path(temp_dir) / "home"  # no .idapro inside
            fake_home.mkdir()
            isolated_root = Path(temp_dir) / "isolated"
            with mock.patch("idalib_mcp.config.Path.home", return_value=fake_home):
                self.assertEqual(_copy_ida_user_state(isolated_root, system="Linux"), [])


if __name__ == "__main__":
    unittest.main()
