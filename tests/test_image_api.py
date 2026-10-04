"""Exercise real multipart HTTP locally; no live provider or user config is used."""

import base64
from contextlib import redirect_stdout
from email import policy
from email.parser import BytesParser
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest.mock import patch

from PIL import Image
import requests


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/image_api.py"


def load_script(path):
    spec = importlib.util.spec_from_file_location("image_api", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


image_api = load_script(SCRIPT)


def png(color, mode="RGB"):
    buffer = io.BytesIO()
    Image.new(mode, (32, 32), color).save(buffer, format="PNG")
    return buffer.getvalue()


class ImageApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.local_home = self.root / "user"
        self.config = self.local_home / ".config/polarisark-product-beautifier/config.yaml"
        self.target = self.root / "商品.png"
        self.target.write_bytes(png("red"))
        self.reference = self.root / "reference.png"
        self.reference.write_bytes(png("blue"))
        self.output_bytes = png("white")
        self.posts, self.gets = [], []
        self.http_status, self.delay = 200, 0
        self.body = {"data": [{"b64_json": base64.b64encode(self.output_bytes).decode()}]}
        test = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                raw = self.rfile.read(int(self.headers["Content-Length"]))
                message = BytesParser(policy=policy.default).parsebytes(
                    ("Content-Type: " + self.headers["Content-Type"] + "\r\n\r\n").encode() + raw)
                parts = [(part.get_param("name", header="content-disposition"),
                          part.get_filename(), part.get_payload(decode=True))
                         for part in message.iter_parts()]
                test.posts.append((self.path, self.headers.get("Authorization"), parts))
                time.sleep(test.delay)
                self.send_response(test.http_status)
                self.send_header("Content-Type", "application/json")
                self.send_header("x-request-id", "mock-request")
                if test.http_status == 302:
                    self.send_header("Location", test.base_url + "/redirected.png")
                self.end_headers()
                try:
                    self.wfile.write(json.dumps(test.body).encode())
                except BrokenPipeError:
                    pass

            def do_GET(self):
                test.gets.append((self.path, self.headers.get("Authorization")))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(test.output_bytes)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.base_url = "http://127.0.0.1:" + str(self.server.server_port)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.home_patch = patch.object(image_api.Path, "home", return_value=self.local_home)
        self.key_patch = patch.dict("os.environ", {"BEAUTIFIER_TEST_KEY": "private-test-key"})
        self.home_patch.start()
        self.key_patch.start()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.thread.join)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.home_patch.stop)
        self.addCleanup(self.key_patch.stop)

    def write_config(self, backend="api"):
        self.config.parent.mkdir(parents=True, exist_ok=True)
        self.config.write_text(
            f"backend: {backend}\napi:\n  base_url: {self.base_url}/v1/\n"
            "  model: vendor-editor\n  api_key_env: BEAUTIFIER_TEST_KEY\n"
            "future_setting: retained\n", encoding="utf-8")

    def invoke(self, args, module=image_api):
        output = io.StringIO()
        with patch.object(module.sys, "stdin", io.StringIO("internal-private-prompt")), redirect_stdout(output):
            code = module.main(args)
        text = output.getvalue()
        self.assertNotIn("private-test-key", text)
        self.assertNotIn("internal-private-prompt", text)
        return code, json.loads(text)

    def edit(self, *extra):
        return self.invoke(["--image", str(self.target), "--out-dir", str(self.root / "candidates"), *extra])

    def test_missing_config_defaults_to_host_without_creating_files(self):
        code, result = self.invoke(["--check"])
        self.assertEqual((code, result["backend"]), (0, "host"))
        self.assertFalse(result["remote_verified"])
        self.assertFalse(self.config.parent.exists())
        code, result = self.edit("--backend", "api")
        self.assertEqual((code, result["code"]), (1, "config_missing"))
        self.assertEqual(self.posts, [])

    def test_explicit_host_ignores_invalid_api_config(self):
        self.write_config()
        self.config.write_text("backend: [broken", encoding="utf-8")
        code, result = self.invoke(["--check", "--backend", "host"])
        self.assertEqual((code, result["backend"]), (0, "host"))
        self.assertEqual(self.config.read_text(), "backend: [broken")

    def test_invalid_or_duplicate_yaml_is_not_treated_as_missing(self):
        self.write_config()
        for content in ("", "[]", "backend: [private-test-key", "backend: api\nbackend: host", "backend: typo"):
            with self.subTest(content=content):
                self.config.write_text(content, encoding="utf-8")
                code, result = self.invoke(["--check"])
                self.assertEqual((code, result["code"]), (1, "config_invalid"))
        self.assertEqual(self.posts, [])

    def test_missing_key_prevents_request(self):
        self.write_config()
        with patch.dict("os.environ", {"BEAUTIFIER_TEST_KEY": ""}):
            code, result = self.edit()
        self.assertEqual((code, result["code"], result["scope"]), (1, "key_missing", "batch"))
        self.assertEqual(self.posts, [])

    def test_key_presence_does_not_select_api(self):
        self.write_config("host")
        code, result = self.edit()
        self.assertEqual((code, result["code"]), (1, "backend_host"))
        self.assertEqual(self.posts, [])

    def test_invalid_endpoint_is_rejected_without_request(self):
        self.write_config()
        for endpoint in ("http://provider.example/v1", "https://user:private-test-key@provider.example/v1",
                         "https://provider.example/v1?key=private-test-key", "https://[invalid"):
            with self.subTest(endpoint=endpoint):
                self.config.write_text("backend: api\napi:\n  base_url: " + endpoint +
                                       "\n  model: vendor-editor\n  api_key_env: BEAUTIFIER_TEST_KEY\n")
                code, result = self.invoke(["--check"])
                self.assertEqual((code, result["code"]), (1, "config_invalid"))
        self.assertEqual(self.posts, [])

    def test_relocation_and_replacement_keep_external_configuration(self):
        self.write_config()
        original = self.config.read_bytes()
        for folder in ("first-install", "updated-install"):
            installed = self.root / folder
            installed.mkdir()
            shutil.copy2(SCRIPT, installed / "image_api.py")
            (installed / "config.yaml").write_text("backend: host")
            module = load_script(installed / "image_api.py")
            code, result = self.invoke(["--check"], module)
            self.assertEqual((code, result["backend"], result["requested_model"]), (0, "api", "vendor-editor"))
            self.assertEqual(result["config_path"], str(self.config))
            self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual(self.posts, [])

    def test_one_multipart_edit_uses_original_then_associated_reference(self):
        self.write_config("host")
        original_config = self.config.read_bytes()
        original_target = self.target.read_bytes()
        code, result = self.edit("--backend", "api", "--reference", str(self.reference),
                                 "--model", "task-editor", "--size", "32x32", "--quality", "high")
        self.assertEqual((code, result["status"], result["qa"]), (0, "candidate", "pending"))
        self.assertNotIn("reported_model", result)
        self.assertEqual((result["width"], result["height"], result["format"]), (32, 32, "png"))
        self.assertEqual(Path(result["image_path"]).read_bytes(), self.output_bytes)
        self.assertEqual(len(self.posts), 1)
        path, authorization, parts = self.posts[0]
        self.assertEqual((path, authorization), ("/v1/images/edits", "Bearer private-test-key"))
        images = [part[2] for part in parts if part[0] == "image[]"]
        self.assertEqual(images, [original_target, self.reference.read_bytes()])
        fields = {name: value for name, filename, value in parts if filename is None}
        self.assertEqual(fields["model"], b"task-editor")
        self.assertEqual(fields["prompt"], b"internal-private-prompt")
        self.assertEqual(fields["n"], b"1")
        self.assertNotIn("input_fidelity", fields)
        self.assertEqual(self.config.read_bytes(), original_config)
        self.assertEqual(self.target.read_bytes(), original_target)
        self.assertEqual(list((self.root / "candidates").glob("*.part")), [])

    def test_url_download_does_not_receive_api_credentials(self):
        self.write_config()
        self.body = {"data": [{"url": "https://cdn.example/image.png"}]}
        real_get = requests.Session.get

        def local_download(session, url, **kwargs):
            self.assertEqual(url, "https://cdn.example/image.png")
            self.assertFalse(session.trust_env)
            return real_get(session, self.base_url + "/image.png", **kwargs)

        with patch.object(requests.Session, "get", local_download):
            code, result = self.edit()
        self.assertEqual((code, result["status"]), (0, "candidate"))
        self.assertEqual(self.gets, [("/image.png", None)])
        self.assertEqual(len(self.posts), 1)

    def test_http_errors_have_scope_and_never_retry(self):
        self.write_config()
        self.body = {"error": {"message": "private-test-key internal-private-prompt"}}
        for status, scope, state in ((400, "item", "failed"), (401, "batch", "failed"),
                                     (404, "batch", "failed"), (429, "batch", "failed"),
                                     (500, "batch", "unknown"), (202, "batch", "unknown"),
                                     (302, "batch", "failed")):
            with self.subTest(status=status):
                self.http_status = status
                before = len(self.posts)
                code, result = self.edit()
                self.assertEqual((code, result["scope"], result["status"]), (1, scope, state))
                self.assertEqual(len(self.posts), before + 1)
        self.assertEqual(self.gets, [])

    def test_download_rejects_embedded_credentials_and_failure_does_not_regenerate(self):
        self.write_config()
        self.body = {"data": [{"url": "https://user:private-test-key@cdn.example/image.png"}]}
        with patch.object(requests.Session, "get") as download:
            code, result = self.edit()
            self.assertEqual((code, result["status"]), (1, "unknown"))
            download.assert_not_called()
        self.body = {"data": [{"url": "https://cdn.example/image.png"}]}
        with patch.object(requests.Session, "get", side_effect=requests.ConnectionError("private-test-key")):
            code, result = self.edit()
        self.assertEqual((code, result["status"]), (1, "unknown"))
        self.assertEqual(len(self.posts), 2)

    def test_reported_model_is_distinct_from_requested_model(self):
        self.write_config()
        self.body["model"] = "reported-vendor-editor"
        code, result = self.edit()
        self.assertEqual((code, result["requested_model"], result["reported_model"]),
                         (0, "vendor-editor", "reported-vendor-editor"))

    def test_read_timeout_is_unknown_and_not_retried(self):
        self.write_config()
        self.delay = 0.15
        code, result = self.edit("--timeout", "0.03")
        self.assertEqual((code, result["status"], result["code"]), (1, "unknown", "request_unknown"))
        self.assertEqual(len(self.posts), 1)

    def test_invalid_source_prevents_request(self):
        self.write_config()
        self.target.write_bytes(b"not an image")
        code, result = self.edit()
        self.assertEqual((code, result["code"]), (1, "image_invalid"))
        self.assertEqual(self.posts, [])

    def test_mask_dimensions_and_alpha_are_checked_before_request(self):
        self.write_config()
        mask = self.root / "mask.png"
        mask.write_bytes(png("white"))
        code, result = self.edit("--mask", str(mask))
        self.assertEqual((code, result["code"]), (1, "mask_invalid"))
        self.assertEqual(self.posts, [])
        mask.write_bytes(png((255, 255, 255, 0), "RGBA"))
        code, result = self.edit("--mask", str(mask))
        self.assertEqual(code, 0)
        self.assertEqual([value for name, _, value in self.posts[0][2] if name == "mask"], [mask.read_bytes()])

    def test_wrong_size_or_format_is_not_saved_as_candidate(self):
        self.write_config()
        for args, error in ((["--size", "64x64"], "size_mismatch"),
                            (["--output-format", "jpeg"], "format_mismatch")):
            with self.subTest(args=args):
                code, result = self.edit(*args)
                self.assertEqual((code, result["code"]), (1, error))
                self.assertEqual(list((self.root / "candidates").iterdir()), [])

    def test_invalid_response_is_unknown_and_not_resubmitted(self):
        self.write_config()
        for body in ({"data": []}, {"data": [{"b64_json": "invalid!!"}]}, []):
            with self.subTest(body=body):
                self.body = body
                before = len(self.posts)
                code, result = self.edit()
                self.assertEqual((code, result["status"]), (1, "unknown"))
                self.assertEqual(len(self.posts), before + 1)

    def test_existing_candidate_is_not_overwritten(self):
        self.write_config()
        candidates = self.root / "candidates"
        candidates.mkdir()
        existing = candidates / "candidate_fixed.png"
        existing.write_bytes(b"existing-file")
        with patch.object(image_api.uuid, "uuid4") as identifier:
            identifier.return_value.hex = "fixed"
            code, result = self.edit()
        self.assertEqual((code, result["status"]), (1, "unknown"))
        self.assertEqual(existing.read_bytes(), b"existing-file")
        self.assertFalse((candidates / "candidate_fixed.part").exists())


if __name__ == "__main__":
    unittest.main()
