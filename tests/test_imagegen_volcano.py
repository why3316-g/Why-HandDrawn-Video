"""火山方舟生图后端：请求构造与结果落盘（离线，mock 网络）。"""
import base64
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import imagegen_volcano as iv


class FakeResp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


class VolcanoImageTests(unittest.TestCase):
    def test_payload_has_refs_as_data_uris_and_no_secret(self):
        with tempfile.TemporaryDirectory() as d:
            ref = Path(d) / 'a.png'; ref.write_bytes(b'\x89PNG fake')
            payload = iv.build_payload('draw', [ref, Path(d) / 'missing.png'])
            self.assertEqual(payload['model'], iv.DEFAULT_MODEL)
            self.assertEqual(len(payload['image']), 1)
            self.assertTrue(payload['image'][0].startswith('data:image/png;base64,'))
            self.assertEqual(payload['response_format'], 'b64_json')
            self.assertFalse(payload['watermark'])
            self.assertNotIn('key', json.dumps(payload).lower())

    def test_generate_writes_image_and_sends_bearer(self):
        seen = {}
        png = b'\x89PNG\r\n\x1a\nfake'

        def opener(req, timeout=0):
            seen['auth'] = req.get_header('Authorization'); seen['url'] = req.full_url
            return FakeResp(json.dumps({'data': [{'b64_json': base64.b64encode(png).decode()}]}).encode())

        with tempfile.TemporaryDirectory() as d:
            out = iv.generate('p', [], Path(d) / 'sub/out.png', 'K123', opener=opener)
            self.assertEqual(out.read_bytes(), png)
        self.assertEqual(seen['auth'], 'Bearer K123')
        self.assertTrue(seen['url'].endswith('/api/v3/images/generations'))

    def test_http_error_never_echoes_key(self):
        def opener(req, timeout=0):
            raise urllib.error.HTTPError(req.full_url, 401, 'x', {}, io.BytesIO(b'{"error":{"message":"bad key"}}'))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError) as cm:
                iv.generate('p', [], Path(d) / 'o.png', 'SECRETKEY', opener=opener)
            self.assertNotIn('SECRETKEY', str(cm.exception))
            self.assertIn('401', str(cm.exception))


if __name__ == '__main__':
    unittest.main()
