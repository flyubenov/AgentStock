from unittest.mock import MagicMock, patch

import services.sheets as sheets


def _fresh(monkeypatch):
    monkeypatch.setattr(sheets, "_service", None)
    monkeypatch.delenv("GOOGLE_SHEETS_CREDS_JSON", raising=False)


def test_falls_back_to_the_runtime_identity_without_json_or_key_file(monkeypatch, tmp_path):
    # Cloud Run: no key exists anywhere; the runtime service account is the identity.
    _fresh(monkeypatch)
    monkeypatch.setenv("GOOGLE_SHEETS_CREDS_PATH", str(tmp_path / "missing.json"))
    adc = MagicMock(name="adc-creds")
    with patch("services.sheets.google.auth.default", return_value=(adc, "proj")) as default, \
         patch("services.sheets.build") as build:
        sheets._get_service()
    default.assert_called_once_with(scopes=sheets.SCOPES)
    assert build.call_args.kwargs["credentials"] is adc


def test_a_present_key_file_still_wins_over_the_runtime_identity(monkeypatch, tmp_path):
    _fresh(monkeypatch)
    key = tmp_path / "sa.json"
    key.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GOOGLE_SHEETS_CREDS_PATH", str(key))
    with patch("services.sheets.service_account.Credentials.from_service_account_file",
               return_value="file-creds") as from_file, \
         patch("services.sheets.google.auth.default") as default, \
         patch("services.sheets.build") as build:
        sheets._get_service()
    from_file.assert_called_once_with(str(key), scopes=sheets.SCOPES)
    default.assert_not_called()
    assert build.call_args.kwargs["credentials"] == "file-creds"


def test_the_json_env_var_wins_over_everything(monkeypatch):
    _fresh(monkeypatch)
    monkeypatch.setenv("GOOGLE_SHEETS_CREDS_JSON", '{"type": "service_account"}')
    with patch("services.sheets.service_account.Credentials.from_service_account_info",
               return_value="json-creds") as from_info, \
         patch("services.sheets.google.auth.default") as default, \
         patch("services.sheets.build"):
        sheets._get_service()
    from_info.assert_called_once_with({"type": "service_account"}, scopes=sheets.SCOPES)
    default.assert_not_called()
