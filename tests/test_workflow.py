from pathlib import Path
import re
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def test_deployment_requires_tests_and_image_scan(self):
        config = yaml.load((ROOT / ".github/workflows/container-deploy.yml").read_text(), Loader=yaml.BaseLoader)
        jobs = config["jobs"]
        self.assertEqual(jobs["build-and-push"]["needs"], "quality")
        self.assertEqual(jobs["deploy"]["needs"], ["build-and-push", "scan-image"])
        self.assertEqual(config["concurrency"]["cancel-in-progress"], "false")
        for job in jobs.values():
            for step in job.get("steps", []):
                if "uses" in step:
                    self.assertRegex(step["uses"], r"@[a-f0-9]{40}$")
                if "run" in step:
                    self.assertNotIn("${{ secrets.", step["run"])

    def test_base_image_is_pinned_and_runtime_has_no_browser(self):
        dockerfile = (ROOT / "Dockerfile").read_text()
        self.assertRegex(dockerfile.splitlines()[0], r"@sha256:[a-f0-9]{64}$")
        self.assertIn("--require-hashes", dockerfile)
        self.assertNotIn("chromium", dockerfile)
        self.assertIn("USER appuser", dockerfile)
