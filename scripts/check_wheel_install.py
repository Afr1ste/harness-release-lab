"""Install outside the checkout and exercise the shipped CLI and pytest fixture."""

import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

wheel = Path(sys.argv[1]).resolve(strict=True)
repository = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="hrl-wheel-") as temp:
    directory = Path(temp)
    venv.EnvBuilder(with_pip=True).create(directory / "venv")
    python = directory / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    def run(*args):
        subprocess.run([str(python), *args], cwd=directory, check=True, timeout=180)

    run("-m", "pip", "install", str(wheel), "pytest")
    run(
        "-I",
        "-c",
        "import importlib.util; assert importlib.util.find_spec('deepseek_harness') is None",
    )
    run("-m", "harness_release_lab.cli", "demo")
    run("-m", "harness_release_lab.cli", "schema", "--output", "schema.json")
    for name in ("service.py", "agent.py", "order.yaml"):
        shutil.copyfile(repository / "examples/http" / name, directory / name)
    (directory / "test_installed.py").write_text(
        "import os, sys\n"
        "import pytest\n"
        "from service import create_app\n"
        "from harness_release_lab.server import local_server\n"
        "@pytest.mark.parametrize('mode,passed', [('fixed',True),('broken',False)])\n"
        "def test_shipped_fixture(hrl_http, tmp_path, mode, passed):\n"
        "    with local_server(create_app(tmp_path / 'db.sqlite')) as url:\n"
        "        report = hrl_http('order.yaml', [sys.executable, 'agent.py', mode],\n"
        "                          env={**os.environ, 'HRL_UPSTREAM': url})\n"
        "    assert report['passed'] is passed, report\n",
        encoding="utf-8",
    )
    run("-m", "pytest", "-q", "test_installed.py")
print("Clean wheel install verified outside repository; optional DSH SDK absent.")
