"""Tests for secure environment-based Alpha Vantage configuration."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from dotenv import load_dotenv

import config


class EnvironmentConfigurationTests(unittest.TestCase):
    """Verify local secret loading and Git safety without real credentials."""

    def test_environment_key_maps_to_news_api_key(self) -> None:
        """Read the configured environment variable without hard-coding a key.

        Returns:
            None.

        Raises:
            None.
        """
        original_value = os.environ.get("ALPHA_VANTAGE_API_KEY")
        try:
            os.environ["ALPHA_VANTAGE_API_KEY"] = "synthetic-test-key"
            reloaded_config = importlib.reload(config)
            self.assertEqual(reloaded_config.NEWS_API_KEY, "synthetic-test-key")
        finally:
            if original_value is None:
                os.environ.pop("ALPHA_VANTAGE_API_KEY", None)
            else:
                os.environ["ALPHA_VANTAGE_API_KEY"] = original_value
            importlib.reload(config)

    def test_currents_environment_key_maps_to_currents_configuration(self) -> None:
        """Read the Currents key from environment without exposing its value.

        Returns:
            None.

        Raises:
            None.
        """
        original_value = os.environ.get("CURRENTS_API_KEY")
        try:
            os.environ["CURRENTS_API_KEY"] = "synthetic-currents-key"
            reloaded_config = importlib.reload(config)
            self.assertEqual(reloaded_config.CURRENTS_API_KEY, "synthetic-currents-key")
        finally:
            if original_value is None:
                os.environ.pop("CURRENTS_API_KEY", None)
            else:
                os.environ["CURRENTS_API_KEY"] = original_value
            importlib.reload(config)

    def test_dotenv_values_can_be_loaded_without_overriding_explicit_environment(self) -> None:
        """Load a synthetic dotenv file using the project dependency.

        Returns:
            None.

        Raises:
            None.
        """
        original_value = os.environ.get("ALPHA_VANTAGE_API_KEY")
        try:
            with tempfile.TemporaryDirectory() as directory:
                dotenv_path = Path(directory) / ".env"
                dotenv_path.write_text("ALPHA_VANTAGE_API_KEY=synthetic-dotenv-key\n", encoding="utf-8")
                os.environ.pop("ALPHA_VANTAGE_API_KEY", None)
                self.assertTrue(load_dotenv(dotenv_path=dotenv_path))
                self.assertEqual(os.environ["ALPHA_VANTAGE_API_KEY"], "synthetic-dotenv-key")
        finally:
            if original_value is None:
                os.environ.pop("ALPHA_VANTAGE_API_KEY", None)
            else:
                os.environ["ALPHA_VANTAGE_API_KEY"] = original_value

    def test_missing_environment_key_maps_to_an_empty_configuration_value(self) -> None:
        """Keep configuration safe when the local dotenv value is blank.

        Returns:
            None.

        Raises:
            None.
        """
        original_value = os.environ.get("ALPHA_VANTAGE_API_KEY")
        try:
            os.environ["ALPHA_VANTAGE_API_KEY"] = ""
            reloaded_config = importlib.reload(config)
            self.assertEqual(reloaded_config.NEWS_API_KEY, "")
        finally:
            if original_value is None:
                os.environ.pop("ALPHA_VANTAGE_API_KEY", None)
            else:
                os.environ["ALPHA_VANTAGE_API_KEY"] = original_value
            importlib.reload(config)

    def test_dotenv_example_contains_only_placeholder(self) -> None:
        """Keep the tracked example useful without containing a credential.

        Returns:
            None.

        Raises:
            None.
        """
        contents = (config.PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertEqual(
            contents,
            "ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key_here\n"
            "CURRENTS_API_KEY=your_currents_api_key_here\n",
        )

    def test_local_dotenv_is_ignored_by_git(self) -> None:
        """Require Git to ignore the local secret file but not its example.

        Returns:
            None.

        Raises:
            None.
        """
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", ".env"],
            cwd=config.PROJECT_ROOT,
            check=False,
        )
        example_ignored = subprocess.run(
            ["git", "check-ignore", "-q", ".env.example"],
            cwd=config.PROJECT_ROOT,
            check=False,
        )

        self.assertEqual(ignored.returncode, 0)
        self.assertNotEqual(example_ignored.returncode, 0)


if __name__ == "__main__":
    unittest.main()
