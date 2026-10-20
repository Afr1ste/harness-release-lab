"""Verify wheel resources without relying on the working tree."""

import sys
import zipfile
from pathlib import Path

wheel = Path(sys.argv[1])
required = {
    "harness_release_lab/data/release.yaml",
    "harness_release_lab/web/index.html",
    "harness_release_lab/dsh_plugin.mjs",
}
with zipfile.ZipFile(wheel) as archive:
    names = set(archive.namelist())
missing = required - names
if missing:
    raise SystemExit(f"Missing packaged resources: {sorted(missing)}")
print(f"Verified {wheel.name}: Python package, scenarios, native plugin, offline report UI")
