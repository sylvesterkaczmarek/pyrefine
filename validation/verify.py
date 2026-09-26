"""Exercise the submitted source and demonstrate failures on its original base."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

CONFIG = json.loads((Path(__file__).with_name("config.json")).read_text())
SOURCE = Path(sys.argv[1]).resolve()
EVIDENCE = Path(__file__).resolve().parents[1] / "evidence"
EVIDENCE.mkdir(exist_ok=True)
PYTHON = sys.executable
ENV = os.environ.copy()
ENV.pop("PYTHONPATH", None)
ENV["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"


def run(name, arguments, cwd=SOURCE, expected_code=0, expected_text=None):
    result = subprocess.run(arguments, cwd=cwd, env=ENV, text=True, capture_output=True)
    output = result.stdout + result.stderr
    (EVIDENCE / (name + ".log")).write_text(output)
    assert result.returncode == expected_code, output[-10000:]
    if expected_text:
        assert expected_text in output, output[-10000:]
    print(name, "PASS" if expected_code == 0 else "EXPECTED FAILURE", flush=True)
    return output


assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SOURCE, text=True).strip() == CONFIG["sha"]
full = [PYTHON] + CONFIG["suite"]
run("submitted-suite", full, expected_text=CONFIG["suite_summary"])
run("gating-lint", [PYTHON, "-m", "flake8"] + CONFIG["lint_paths"] + ["--select=E9,F63,F7,F82"])
run("new-test-lint", [PYTHON, "-m", "flake8", CONFIG["test_path"], "--max-line-length=119"])
fixed = {path: (SOURCE / path).read_bytes() for path in CONFIG["source_paths"]}
try:
    for path in fixed:
        (SOURCE / path).write_bytes(subprocess.check_output(
            ["git", "show", CONFIG["base"] + ":" + path], cwd=SOURCE))
    output = run("original-regressions", [PYTHON] + CONFIG["regressions"],
                 expected_code=1, expected_text=CONFIG["regression_summary"])
    assert "ImportError while importing test module" not in output
finally:
    for path, content in fixed.items():
        (SOURCE / path).write_bytes(content)
run("restored-suite", full, expected_text=CONFIG["suite_summary"])
run("patch-check", ["git", "diff", "--check", CONFIG["base"] + "...HEAD"])
run("source-restoration", ["git", "diff", "--exit-code"])
run("package-build", [PYTHON, "-m", "build"] + CONFIG["build_args"] + ["--outdir", str(EVIDENCE / "dist")])
wheel = next((EVIDENCE / "dist").glob("*.whl"))
run("install-built-wheel", [PYTHON, "-m", "pip", "install", "--no-index", "--no-deps", "--force-reinstall", str(wheel)])
with tempfile.TemporaryDirectory() as directory:
    code = CONFIG["installed_test_code"].replace("TEST_PATH", repr(str(SOURCE / CONFIG["test_path"])))
    run("installed-wheel-tests", [PYTHON, "-c", code], cwd=directory, expected_text=CONFIG["installed_summary"])
run("dependencies", [PYTHON, "-m", "pip", "freeze"])
run("dependency-check", [PYTHON, "-m", "pip", "check"])
(EVIDENCE / "submission.json").write_text(json.dumps(CONFIG, indent=2))
print(CONFIG["final_summary"], flush=True)
