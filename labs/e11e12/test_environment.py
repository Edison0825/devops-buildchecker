"""Exercise the Dockerfile's mirror substitution without a Docker daemon."""

import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

DOCKERFILE = Path(__file__).parent / "environment/services/buildchecker/Dockerfile"


class EnvironmentMirrorTests(unittest.TestCase):
    def check_mirror(self, mirror):
        dockerfile = DOCKERFILE.read_text()
        if mirror is None:
            mirror = next(
                line.split("=", 1)[1]
                for line in dockerfile.splitlines()
                if line.startswith("ARG APT_MIRROR=")
            )
        # Execute the actual substitution, stopping before package installation.
        script = (
            "sed -E -i.bak "
            + dockerfile.split("RUN sed -E -i ", 1)[1].split(" && apt-get", 1)[0]
        )
        with tempfile.TemporaryDirectory() as d:
            sources = Path(d) / "debian.sources"
            sources.write_text(
                "Types: deb\n"
                "URIs: http://deb.debian.org/debian https://deb.debian.org/debian\n"
                "Suites: trixie trixie-updates\n"
                "Components: main\n"
                "Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg\n\n"
                "Types: deb\n"
                "URIs: http://deb.debian.org/debian-security "
                "https://deb.debian.org/debian-security "
                "http://security.debian.org/debian-security "
                "https://security.debian.org/debian-security\n"
                "Suites: trixie-security\n"
                "Components: main\n"
                "Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg\n"
            )
            script = script.replace(
                "/etc/apt/sources.list.d/debian.sources", shlex.quote(str(sources))
            )
            subprocess.run(
                ["sh", "-c", script],
                env=dict(os.environ, APT_MIRROR=mirror),
                check=True,
                capture_output=True,
                text=True,
            )
            result = sources.read_text()
        self.assertIn(f"URIs: {mirror}/debian {mirror}/debian\n", result)
        self.assertIn(
            "URIs: " + " ".join([f"{mirror}/debian-security"] * 4) + "\n", result
        )
        self.assertNotIn("debian-security-security", result)
        self.assertIn("Suites: trixie trixie-updates\n", result)
        self.assertIn("Suites: trixie-security\n", result)
        self.assertEqual(
            result.count("Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg"), 2
        )

    def test_default_server_mirror(self):
        self.check_mirror(None)

    def test_ci_official_mirror(self):
        self.check_mirror("https://deb.debian.org")


if __name__ == "__main__":
    unittest.main()
