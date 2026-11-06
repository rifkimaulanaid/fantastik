"""Exercise deployment control flow against a fake Docker executable only."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GIT_BASH = Path("C:/Program Files/Git/bin/bash.exe")
BASH = str(GIT_BASH) if os.name == "nt" and GIT_BASH.exists() else shutil.which("bash")
REVISION = "a" * 40
IMAGE = "ghcr.io/example/fantastik@sha256:" + "b" * 64
OLD = "sha256:" + "c" * 64


def posix(path):
    path = Path(path).resolve()
    return "/" + path.drive[0].lower() + path.as_posix()[2:] if os.name == "nt" else str(path)


FAKE_DOCKER = r'''#!/usr/bin/env bash
set -eu
printf '%s | %s\n' "${APP_IMAGE:-unset}" "$*" >> "$TEST_LOG"
case "$*" in
  "compose --env-file .env ps -q fantastik")
    if [ -f .mutated ]; then echo new-container; else echo old-container; fi ;;
  "inspect --format {{.Image}} old-container") echo "$TEST_OLD" ;;
  "image inspect --format "*) echo "$TEST_REVISION" ;;
  "inspect --format "*)
    if [ "${FAIL_AFTER:-0}" = 1 ]; then echo wrong; else echo "$TEST_REVISION"; fi ;;
  "compose --env-file .env up "*)
    touch .mutated
    if [ "${FAIL_UP:-0}" = 1 ] && [ "$APP_IMAGE" != "$TEST_OLD" ]; then exit 1; fi ;;
  "run "*) if [ "${FAIL_SMOKE:-0}" = 1 ]; then exit 1; fi ;;
esac
'''


@unittest.skipUnless(BASH, "Bash required for deployment control-flow tests")
class DeploymentTests(unittest.TestCase):
    def run_deployment(self, directory, *, image=IMAGE, **extra):
        folder = Path(directory)
        binary = folder / "bin"
        binary.mkdir(exist_ok=True)
        fake = binary / "docker"
        fake.write_text(FAKE_DOCKER, encoding="utf-8", newline="\n")
        fake.chmod(0o755)
        if os.name == "nt":
            # Git Bash lacks util-linux flock. Locking itself is exercised by
            # the Linux CI job; this stub only enables control-flow tests here.
            (binary / "flock").write_text("#!/usr/bin/env bash\nexit 0\n", newline="\n")
        (folder / ".env").write_text("APP_PORT=8501\n")
        log = folder / "docker.log"
        env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ["PATH"],
                   TEST_LOG=posix(log), TEST_OLD=OLD, TEST_REVISION=REVISION, **extra)
        completed = subprocess.run([BASH, posix(ROOT / "scripts/deploy.sh"), posix(folder), image, REVISION],
                                   env=env, capture_output=True, text=True, timeout=15)
        return completed, log.read_text() if log.exists() else ""

    def test_success_persists_exact_digest_after_wait_and_smoke(self):
        with tempfile.TemporaryDirectory() as directory:
            completed, log = self.run_deployment(directory)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual((Path(directory) / ".release.env").read_text(), f"APP_IMAGE={IMAGE}\n")
            self.assertIn("--wait --wait-timeout 90", log)
            self.assertIn("--network none", log)
            self.assertNotIn("prune", log)

    def test_health_failure_restores_previous_immutable_image(self):
        with tempfile.TemporaryDirectory() as directory:
            completed, log = self.run_deployment(directory, FAIL_UP="1")
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn(OLD + " | compose", log)
            self.assertIn("--pull never", log)
            self.assertFalse((Path(directory) / ".release.env").exists())

    def test_wrong_running_revision_triggers_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            completed, log = self.run_deployment(directory, FAIL_AFTER="1")
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn(OLD + " | compose", log)

    def test_smoke_failure_does_not_replace_existing_container(self):
        with tempfile.TemporaryDirectory() as directory:
            completed, log = self.run_deployment(directory, FAIL_SMOKE="1")
            self.assertNotEqual(completed.returncode, 0)
            self.assertNotIn("compose --env-file .env up", log)

    def test_unpinned_image_rejected_before_docker(self):
        with tempfile.TemporaryDirectory() as directory:
            completed, log = self.run_deployment(directory, image="ghcr.io/example/fantastik:latest")
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(log, "")
