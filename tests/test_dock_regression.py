"""Regression tests for v1.0.2 dock-launch failure (1.0.3 fix)."""
import ast
import os
import pathlib
import unittest
from unittest.mock import MagicMock, patch

REPO = pathlib.Path(__file__).resolve().parent.parent


class TestGLibShadowing(unittest.TestCase):
    def test_no_local_glib_import_in_init(self):
        tree = ast.parse((REPO / "wallshuffle" / "app.py").read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "WallpaperApp":
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                        for sub in ast.walk(item):
                            if isinstance(sub, ast.ImportFrom) and sub.module == "gi.repository":
                                for a in sub.names:
                                    self.assertNotEqual(
                                        a.name, "GLib", "local GLib import shadows global (dock crash)"
                                    )

    def test_no_noqa_f823(self):
        text = (REPO / "wallshuffle" / "app.py").read_text()
        self.assertNotIn("noqa: F823", text)
        self.assertNotIn("noqa: F821", text)
        self.assertNotIn("noqa: F822", text)

    def test_app_imports_cleanly(self):
        import wallshuffle.app  # noqa: F401 - smoke: UI split must import

    def test_single_instance_no_sys_exit_in_vfunc(self):
        text = (REPO / "wallshuffle" / "app.py").read_text()
        # do_startup must quit via GLib.idle_add, never sys.exit() call in vfunc.
        startup = text.split("def do_startup")[1].split("def do_activate")[0]
        self.assertNotIn("sys.exit(", startup)
        self.assertIn("GLib.idle_add(self.quit)", startup)

    def test_wakeup_routes_to_activate(self):
        text = (REPO / "wallshuffle" / "app.py").read_text()
        self.assertNotIn("present_window", text)
        self.assertIn("def do_open", text)


class TestPackaging(unittest.TestCase):
    def test_pyproject_includes_subpackages(self):
        text = (REPO / "pyproject.toml").read_text()
        self.assertIn('include = ["wallshuffle*"]', text)

    def test_desktop_activation_contract(self):
        from wallshuffle.constants import APPLICATION_ID

        desktop = (REPO / "data" / "io.github.kayab999.WallShuffle.desktop").read_text()
        self.assertIn(f"StartupWMClass={APPLICATION_ID}", desktop)
        # No DBusActivatable without a dbus-1 .service file: launchers would
        # attempt D-Bus activation and never Exec the binary (silent no-open).
        self.assertNotIn("DBusActivatable", desktop)
        self.assertTrue((REPO / "data" / "io.github.kayab999.WallShuffle.png").exists())

    def test_lazy_init(self):
        text = (REPO / "wallshuffle" / "__init__.py").read_text()
        self.assertIn("__getattr__", text)
        self.assertNotIn("from .core import", text.split("__getattr__")[0].replace("__version__", ""))


class TestTimerPaths(unittest.TestCase):
    def test_prefers_stable_appimage_over_transient_which(self):
        from wallshuffle import system_integration as si

        with patch.dict(os.environ, {"APPIMAGE": "/tmp/.mount_ABC/usr/bin/wallshuffle"}):
            with patch("wallshuffle.system_integration.shutil.which", return_value="/tmp/.mount_ABC/usr/bin/wallshuffle"):
                with patch("os.path.isfile", return_value=True), patch("os.access", return_value=True):
                    # Transient mount must never be persisted
                    result = si._find_executable_for_timer()
                    self.assertFalse(result.startswith("/tmp/.mount"))

    def test_cron_quotes_exec_with_space(self):
        from wallshuffle.system_integration import setup_cron_fallback

        with patch("wallshuffle.system_integration._find_executable_for_timer", return_value="/tmp/my apps/wallshuffle"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="")
                setup_cron_fallback(30, False, MagicMock())
                written = mock_run.call_args_list[-1].kwargs.get("input", "")
                self.assertIn("'/tmp/my apps/wallshuffle' --change", written)
                self.assertIn("WALLSHUFFLE_TIMER", written)


class TestUnsplashAuth(unittest.TestCase):
    def test_key_sent_via_header_not_url(self):
        from wallshuffle.online_sources import OnlineSourceManager

        cm = MagicMock()
        cm.get_setting.side_effect = lambda c, s, o, fb=None, vt=str: {
            "circuit_breaker_failures": 3,
            "circuit_breaker_cooldown": 15,
            "max_cache_size_mb": 500,
            "unsplash_api_key": "SECRET123",
        }.get(o, fb)
        mgr = OnlineSourceManager.__new__(OnlineSourceManager)
        mgr.config_manager = cm
        mgr.config = {}
        mgr.max_failures = 3
        mgr.cooldown_minutes = 15
        mgr.max_cache_size_mb = 500
        import requests as _rq

        mgr.session = _rq.Session()
        with patch.object(mgr, "_get_cached_image", return_value=None):
            with patch.object(mgr, "_check_circuit_breaker", return_value=True):
                with patch.object(mgr.session, "get") as mock_get:
                    resp = MagicMock()
                    resp.json.return_value = {"urls": {"full": "https://example/img.jpg"}}
                    resp.headers = {}
                    img = MagicMock()
                    img.headers = {}
                    img.iter_content.return_value = [b"x"]
                    mock_get.side_effect = [resp, img]
                    with patch.object(OnlineSourceManager, "_save_image_file_to_cache"), patch.object(
                        OnlineSourceManager, "cleanup_old_cache"
                    ):
                        with patch("tempfile.NamedTemporaryFile") as mock_tmp:
                            mf = MagicMock()
                            mf.name = "/tmp/x.jpg"
                            mock_tmp.return_value = mf
                            try:
                                mgr.fetch_unsplash_wallpaper("nature")
                            except Exception:
                                pass
                    first_url = mock_get.call_args_list[0].args[0]
                    first_headers = mock_get.call_args_list[0].kwargs.get("headers", {})
                    self.assertNotIn("SECRET123", first_url)
                    self.assertNotIn("client_id", first_url)
                    self.assertEqual(first_headers.get("Authorization"), "Client-ID SECRET123")


if __name__ == "__main__":
    unittest.main()
