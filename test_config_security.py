import copy
import json
import unittest
from unittest.mock import patch

import config


class FakeKeyring:
    def __init__(self, fail_set: bool = False):
        self.fail_set = fail_set
        self.store = {}

    def set_password(self, service_name: str, username: str, password: str):
        if self.fail_set:
            raise RuntimeError("set_password failed")
        self.store[(service_name, username)] = password

    def get_password(self, service_name: str, username: str):
        return self.store.get((service_name, username))

    def delete_password(self, service_name: str, username: str):
        self.store.pop((service_name, username), None)


class TestGoogleDriveTokenSecurity(unittest.TestCase):
    def _build_settings(self) -> dict:
        settings = copy.deepcopy(config.DEFAULT_SETTINGS)
        settings["instance_id"] = "instance-1"
        return settings

    @patch("config.save_settings", return_value=True)
    @patch("config.load_settings")
    def test_update_google_drive_auth_stores_tokens_in_keyring_when_available(self, mock_load_settings, mock_save_settings):
        settings = self._build_settings()
        mock_load_settings.return_value = settings
        fake_keyring = FakeKeyring()

        with patch("config._get_keyring_module", return_value=fake_keyring):
            ok = config.update_google_drive_auth(
                {
                    "connected": True,
                    "access_token": "access-1",
                    "refresh_token": "refresh-1",
                }
            )

        self.assertTrue(ok)
        saved_settings = mock_save_settings.call_args.args[0]
        saved_auth = saved_settings["google_drive"]["auth"]
        self.assertTrue(saved_auth["tokens_in_keyring"])
        self.assertEqual(saved_auth["access_token"], "")
        self.assertEqual(saved_auth["refresh_token"], "")

        secret_user = "instance-1:google_drive_auth"
        raw_payload = fake_keyring.get_password(config.GOOGLE_DRIVE_TOKEN_KEYRING_SERVICE, secret_user)
        self.assertIsNotNone(raw_payload)
        payload = json.loads(raw_payload)
        self.assertEqual(payload["access_token"], "access-1")
        self.assertEqual(payload["refresh_token"], "refresh-1")

    @patch("config.save_settings", return_value=True)
    @patch("config.load_settings")
    def test_update_google_drive_auth_falls_back_to_plaintext_when_keyring_write_fails(
        self,
        mock_load_settings,
        mock_save_settings,
    ):
        settings = self._build_settings()
        mock_load_settings.return_value = settings
        fake_keyring = FakeKeyring(fail_set=True)

        with patch("config._get_keyring_module", return_value=fake_keyring):
            ok = config.update_google_drive_auth(
                {
                    "connected": True,
                    "access_token": "access-2",
                    "refresh_token": "refresh-2",
                }
            )

        self.assertTrue(ok)
        saved_settings = mock_save_settings.call_args.args[0]
        saved_auth = saved_settings["google_drive"]["auth"]
        self.assertFalse(saved_auth["tokens_in_keyring"])
        self.assertEqual(saved_auth["access_token"], "access-2")
        self.assertEqual(saved_auth["refresh_token"], "refresh-2")

    @patch("config.load_settings")
    def test_get_google_drive_settings_reads_tokens_from_keyring(self, mock_load_settings):
        settings = self._build_settings()
        settings["google_drive"]["auth"]["connected"] = True
        settings["google_drive"]["auth"]["tokens_in_keyring"] = True
        settings["google_drive"]["auth"]["access_token"] = ""
        settings["google_drive"]["auth"]["refresh_token"] = ""
        mock_load_settings.return_value = settings

        fake_keyring = FakeKeyring()
        secret_user = "instance-1:google_drive_auth"
        fake_keyring.set_password(
            config.GOOGLE_DRIVE_TOKEN_KEYRING_SERVICE,
            secret_user,
            json.dumps({"access_token": "stored-access", "refresh_token": "stored-refresh"}),
        )

        with patch("config._get_keyring_module", return_value=fake_keyring):
            google_drive = config.get_google_drive_settings()

        auth = google_drive["auth"]
        self.assertEqual(auth["access_token"], "stored-access")
        self.assertEqual(auth["refresh_token"], "stored-refresh")

    @patch("config.save_settings", return_value=True)
    @patch("config.load_settings")
    def test_clear_google_drive_auth_removes_keyring_tokens(self, mock_load_settings, mock_save_settings):
        settings = self._build_settings()
        mock_load_settings.return_value = settings

        fake_keyring = FakeKeyring()
        secret_user = "instance-1:google_drive_auth"
        fake_keyring.set_password(
            config.GOOGLE_DRIVE_TOKEN_KEYRING_SERVICE,
            secret_user,
            json.dumps({"access_token": "old-access", "refresh_token": "old-refresh"}),
        )

        with patch("config._get_keyring_module", return_value=fake_keyring):
            ok = config.clear_google_drive_auth()

        self.assertTrue(ok)
        self.assertIsNone(fake_keyring.get_password(config.GOOGLE_DRIVE_TOKEN_KEYRING_SERVICE, secret_user))


if __name__ == "__main__":
    unittest.main()
