from __future__ import annotations

import os
from pathlib import Path


# Set the isolated database before pytest imports any application module.
TEST_DATABASE_PATH = Path(__file__).parent / "test_perimetr.db"
os.environ["PERIMETR_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["PERIMETR_ENV"] = "development"
os.environ["PERIMETR_PUBLIC_URL"] = "http://localhost:18080"
os.environ["PERIMETR_SESSION_TTL_SEC"] = "3600"
os.environ["PERIMETR_POD_BUNDLE_SOURCE"] = "/tmp/perimetr-pod-test-bundle"
os.environ["PERIMETR_POD_CACHE_DIR"] = "/tmp/perimetr-pod-test-cache"
os.environ["KERNEL_URL"] = ""
os.environ["KERNEL_SERVICE_TOKEN"] = ""
os.environ["UPDATER_CONTROL_TOKEN"] = "test-updater-control-token-32-characters"
