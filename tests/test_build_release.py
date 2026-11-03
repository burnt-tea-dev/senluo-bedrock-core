import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "tools/build_release.py"
spec = importlib.util.spec_from_file_location("core_release", SOURCE)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseScopeTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        files = {"LICENSE": b"License remains unchanged\n", "src/core.js": b"export const value = 1;\n",
                 "tools/install_cookery.py": b"# Current toolkit installer\n"}
        sha = lambda raw: hashlib.sha256(raw).hexdigest()
        sdk = {"version": "0.1.0", "files": {"scripts/core.js": {
            "source": "src/core.js", "sha256": sha(files["src/core.js"])}}}
        files["sdk.json"] = json.dumps(sdk).encode()
        files["package.json"] = b'{"version":"0.8.0"}'
        names = [*files, "PUBLICATION.json", "release-history.json"]
        files["PUBLICATION.json"] = json.dumps({"files": names}).encode()
        old_payloads = {name: sha(files[name]) for name in ("LICENSE", "sdk.json", "src/core.js")}
        old_payloads["tools/install_cookery.py"] = sha(b"# Historical installer\n")
        history = {"0.1.0": {"payloads": old_payloads}, "0.8.0": {
            "toolkit_version": "0.8.0", "sdk_version": "0.1.0",
            "payloads": {name: sha(raw) for name, raw in files.items()}}}
        files["release-history.json"] = json.dumps(history).encode()
        for name, raw in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        original_root = release.ROOT
        self.addCleanup(setattr, release, "ROOT", original_root)
        release.ROOT = root
        return root, history

    def test_current_toolkit_can_update_installer_with_unchanged_sdk(self):
        _, history = self.fixture()
        sdk, _, old, toolkit_version = release.validate()
        self.assertEqual(sdk["version"], "0.1.0")
        self.assertEqual(toolkit_version, "0.8.0")
        self.assertEqual(old, history["0.1.0"])

    def test_new_toolkit_does_not_allow_old_sdk_bytes_to_change(self):
        root, history = self.fixture()
        raw = b"export const value = 2;\n"
        (root / "src/core.js").write_bytes(raw)
        history["0.8.0"]["payloads"]["src/core.js"] = hashlib.sha256(raw).hexdigest()
        (root / "release-history.json").write_text(json.dumps(history))
        with self.assertRaisesRegex(ValueError, "src/core.js"):
            release.validate()

    def test_additional_tracked_ci_and_test_files_are_not_publication_inputs(self):
        root, _ = self.fixture()
        extra = root / '.github/workflows/ci.yml'
        extra.parent.mkdir(parents=True, exist_ok=True)
        extra.write_text('name: developer CI only\n')
        subprocess.run(['git', 'add', '.github/workflows/ci.yml'], cwd=root, check=True)
        _, names, _, _ = release.validate()
        self.assertNotIn('.github/workflows/ci.yml', names)
        self.assertIn('tools/install_cookery.py', names)
