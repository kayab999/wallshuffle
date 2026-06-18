import unittest
from unittest.mock import MagicMock, patch

from wallshuffle.system_integration import _find_executable_for_timer, setup_cron_fallback


class TestSystemIntegration(unittest.TestCase):
    def test_find_executable_prefers_path(self):
        with patch("wallshuffle.system_integration.shutil.which", return_value="/usr/bin/wallshuffle"):
            self.assertEqual(_find_executable_for_timer(), "/usr/bin/wallshuffle")

    @patch("subprocess.run")
    def test_setup_cron_fallback_writes_crontab(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="# existing\n")
        with patch("wallshuffle.system_integration._find_executable_for_timer", return_value="/usr/bin/wallshuffle"):
            result = setup_cron_fallback(30, True, MagicMock())
        self.assertTrue(result)
        write_call = mock_run.call_args_list[-1]
        written = write_call.kwargs.get("input") or (write_call.args[0] if write_call.args else "")
        self.assertIn("WALLSHUFFLE_TIMER", written)
        self.assertIn("/usr/bin/wallshuffle", written)


if __name__ == "__main__":
    unittest.main()
