"""Verify the upload allowlist and content-based file reuse without OCI access."""
import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import oci_vector_store_upload as uploader


class UploadTests(unittest.TestCase):
    def run_upload(self, reuse):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in uploader.DOCUMENTS + ("demo_questions.md",):
                (root / name).write_text("fictional content", encoding="utf-8")
            config = root / "settings.json"
            config.write_text(json.dumps({"region": "demo-region", "project_id": "demo-project",
                                          "compartment_id": "demo-compartment", "vector_store_id": "demo-store"}))
            digest = hashlib.sha256(b"fictional content").hexdigest()
            files = [{"filename": f"{Path(name).stem}-{digest}.md", "id": f"demo-file-{index}"}
                     for index, name in enumerate(uploader.DOCUMENTS)]
            session = MagicMock()
            uploaded_names = []
            attached_ids = []

            def request(method, url, **kwargs):
                result = MagicMock()
                if method == "GET" and url.endswith("/vector_stores/demo-store/files"):
                    data = {"data": [], "has_more": False}
                elif method == "GET" and url.endswith("/files"):
                    data = {"data": files if reuse else [], "has_more": False}
                elif method == "POST" and url.endswith("/vector_stores/demo-store/files"):
                    attached_ids.append(kwargs["json"]["file_id"])
                    data = {"status": "in_progress"}
                elif method == "POST" and url.endswith("/files"):
                    uploaded_names.append(kwargs["files"]["file"][0])
                    data = {"id": f"demo-file-{len(uploaded_names) - 1}"}
                elif method == "GET" and "/files/demo-file-" in url:
                    data = {"status": "completed"}
                else:
                    raise AssertionError(f"Unexpected request: {method}")
                result.json.return_value = data
                return result

            session.request.side_effect = request
            with patch.object(uploader.requests, "Session") as factory, patch.object(
                uploader.oci.auth.signers, "InstancePrincipalsSecurityTokenSigner"
            ), patch.dict("os.environ", {}, clear=True), patch("sys.argv", [
                "upload", "upload", "--settings", str(config), "--directory", str(root)
            ]), redirect_stdout(StringIO()):
                factory.return_value.__enter__.return_value = session
                uploader.main()
            return uploaded_names, attached_ids, files

    def test_uploads_only_three_knowledge_documents(self):
        uploaded, attached, files = self.run_upload(reuse=False)
        self.assertEqual(uploaded, [item["filename"] for item in files])
        self.assertEqual(len(attached), 3)
        self.assertTrue(all("demo_questions" not in name for name in uploaded))

    def test_unchanged_documents_reuse_files(self):
        uploaded, attached, files = self.run_upload(reuse=True)
        self.assertEqual(uploaded, [])
        self.assertEqual(attached, [item["id"] for item in files])


if __name__ == "__main__":
    unittest.main()
