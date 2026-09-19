"""Validate the actual Compose-parsed environment as the runtime UID."""
from .settings import Settings
from .security import validate_runtime_settings, is_password_hash
from pathlib import Path


def main():
    settings = Settings(_env_file=None)
    if settings.perimetr_version != (Path(__file__).resolve().parents[1] / 'VERSION').read_text().strip():
        raise SystemExit("Configured release version differs from the installed image")
    validate_runtime_settings(settings)
    if settings.perimetr_access_key in {None, ""} and not is_password_hash(settings.perimetr_access_key_hash):
        raise SystemExit("Set the initial PERIMETR_ACCESS_KEY explicitly. Its exact value is preserved.")
    print("Runtime configuration is valid; secret values are not displayed.")


if __name__ == "__main__":
    main()
