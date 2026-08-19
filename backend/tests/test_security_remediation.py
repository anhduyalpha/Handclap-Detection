import os
import unittest
from pathlib import Path
from fastapi import HTTPException
from app.core.security import (
    safe_path_resolve,
    sanitize_identifier,
    validate_outbound_url,
    verify_studio_token,
    ALLOWED_CHECKPOINT_FILENAMES
)
from app.config import USER_PROFILES_DIR, CHECKPOINTS_DIR

class TestSecurityRemediation(unittest.TestCase):
    def test_sanitize_identifier_valid(self):
        self.assertEqual(sanitize_identifier("default"), "default")
        self.assertEqual(sanitize_identifier("my_model-123"), "my_model-123")
        self.assertEqual(sanitize_identifier("user_profile_v2"), "user_profile_v2")

    def test_sanitize_identifier_invalid(self):
        invalid_cases = [
            "../traversal",
            "../../etc/passwd",
            "..\\windows",
            "profile/sub",
            "test;rm -rf /",
            "name with spaces",
            "<script>alert(1)</script>",
            "",
            None
        ]
        for case in invalid_cases:
            with self.assertRaises(HTTPException) as ctx:
                sanitize_identifier(case)
            self.assertIn(ctx.exception.status_code, (400, 403))

    def test_safe_path_resolve_valid(self):
        base = USER_PROFILES_DIR
        resolved = safe_path_resolve(base, "default", "claps", "sample_001.wav")
        self.assertTrue(resolved.is_relative_to(base.resolve()))
        self.assertEqual(resolved.name, "sample_001.wav")

    def test_safe_path_resolve_traversal_blocked(self):
        base = USER_PROFILES_DIR
        traversal_cases = [
            ("..", "etc", "passwd"),
            ("default", "..", "..", "config.py"),
            ("../../../Windows/win.ini",),
            ("default/../../data",)
        ]
        for parts in traversal_cases:
            with self.assertRaises(HTTPException) as ctx:
                safe_path_resolve(base, *parts)
            self.assertIn(ctx.exception.status_code, (400, 403))

    def test_validate_outbound_url_valid(self):
        valid_urls = [
            "http://127.0.0.1:8000/api/test",
            "http://localhost:8123/api/webhook/clap",
            "https://api.telegram.org/bot123/sendMessage",
            "http://192.168.1.50:8080/hook"
        ]
        for url in valid_urls:
            validated = validate_outbound_url(url)
            self.assertEqual(validated, url)

    def test_validate_outbound_url_ssrf_blocked(self):
        # Cloud Metadata IP
        with self.assertRaises(HTTPException) as ctx:
            validate_outbound_url("http://169.254.169.254/latest/meta-data")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertTrue("SSRF" in ctx.exception.detail or "blocked" in ctx.exception.detail.lower())

        # Invalid scheme
        with self.assertRaises(HTTPException) as ctx:
            validate_outbound_url("file:///etc/passwd")
        self.assertEqual(ctx.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx:
            validate_outbound_url("gopher://127.0.0.1:6379")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_checkpoint_filenames_whitelist(self):
        self.assertIn("model_cnn.pt", ALLOWED_CHECKPOINT_FILENAMES)
        self.assertIn("model_sklearn.joblib", ALLOWED_CHECKPOINT_FILENAMES)
        self.assertIn("scaler.joblib", ALLOWED_CHECKPOINT_FILENAMES)
        self.assertIn("meta.json", ALLOWED_CHECKPOINT_FILENAMES)
        self.assertNotIn("exploit.sh", ALLOWED_CHECKPOINT_FILENAMES)
        self.assertNotIn("model.py", ALLOWED_CHECKPOINT_FILENAMES)
        self.assertNotIn("../../etc/passwd", ALLOWED_CHECKPOINT_FILENAMES)

    def test_verify_studio_token(self):
        os.environ.pop("STUDIO_API_TOKEN", None)
        self.assertTrue(verify_studio_token())

        os.environ["STUDIO_API_TOKEN"] = "super-secret-token-12345"
        try:
            self.assertTrue(verify_studio_token("super-secret-token-12345"))

            with self.assertRaises(HTTPException) as ctx:
                verify_studio_token("wrong-token")
            self.assertEqual(ctx.exception.status_code, 401)

            with self.assertRaises(HTTPException) as ctx:
                verify_studio_token(None)
            self.assertEqual(ctx.exception.status_code, 401)
        finally:
            os.environ.pop("STUDIO_API_TOKEN", None)

if __name__ == "__main__":
    unittest.main()
