"""Regression tests for HTTP request header rewriting."""
import importlib
import importlib.machinery
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


# Load the proxy module without running the package initializer, which imports
# the optional Windows packet-interception driver used by the proxy manager.
_package_spec = importlib.machinery.ModuleSpec(
    "_steamdl_proxy_tests", loader=None, is_package=True
)
_package_spec.submodule_search_locations = [
    str(Path(__file__).resolve().parents[1] / "proxy")
]
with patch.dict(sys.modules):
    sys.modules[_package_spec.name] = importlib.util.module_from_spec(_package_spec)
    TransparentProxy = importlib.import_module(
        "_steamdl_proxy_tests.transparent_proxy"
    ).TransparentProxy


class HeaderRewriteTests(unittest.TestCase):
    def setUp(self):
        # Header rewriting does not require starting the proxy or reading rx.txt.
        self.proxy = TransparentProxy.__new__(TransparentProxy)
        self.proxy.cache_domain = "cache.example.com"
        self.proxy.token = "test-token"

    def test_removes_user_agent_case_insensitively(self):
        for name in (b"User-Agent", b"user-agent", b"USER-AGENT", b"uSeR-aGeNt"):
            with self.subTest(name=name):
                request = (
                    b"GET /depot/chunk HTTP/1.1\r\n"
                    b"Host: steam.example.com\r\n"
                    + name + b": Valve/Steam HTTP Client 1.0\r\n\r\n"
                )

                result = self.proxy._modify_headers(request)

                self.assertNotIn(b"user-agent", result.lower())
                self.assertNotIn(b"Valve/Steam", result)

    def test_removes_all_user_agent_headers_and_preserves_other_headers(self):
        request = (
            b"GET /depot/chunk HTTP/1.1\r\n"
            b"Host: steam.example.com\r\n"
            b"User-Agent: Valve/Steam HTTP Client 1.0\r\n"
            b"Range: bytes=0-1023\r\n"
            b"user-agent: duplicate\r\n"
            b"USER-AGENT:\r\n"
            b"Connection: keep-alive\r\n\r\n"
        )

        self.assertEqual(
            self.proxy._modify_headers(request),
            b"GET /depot/chunk HTTP/1.1\r\n"
            b"Host: cache.example.com\r\n"
            b"Range: bytes=0-1023\r\n"
            b"Connection: keep-alive\r\n"
            b"Real-Host: steam.example.com\r\n"
            b"Auth-Token: test-token\r\n\r\n",
        )

    def test_does_not_add_user_agent_when_absent(self):
        request = b"GET /depot/chunk HTTP/1.1\r\nAccept: */*\r\n\r\n"

        self.assertEqual(
            self.proxy._modify_headers(request),
            b"GET /depot/chunk HTTP/1.1\r\n"
            b"Host: cache.example.com\r\n"
            b"Accept: */*\r\n"
            b"Real-Host: cache.example.com\r\n"
            b"Auth-Token: test-token\r\n\r\n",
        )


if __name__ == "__main__":
    unittest.main()
