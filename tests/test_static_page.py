"""The single-file page carries the whole payload and needs nothing from the server."""
import base64
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from back.api import static_page


class StaticPageTest(unittest.TestCase):
    def test_assets_and_data_are_inlined(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / 'dist'
            (dist / 'assets').mkdir(parents=True)
            (dist / 'index.html').write_text('<head><script type="module" crossorigin src="/assets/index-a.js"></script>\n'
                                             '<link rel="stylesheet" crossorigin href="/assets/index-b.css"></head><body></body>')
            (dist / 'assets' / 'index-a.js').write_text('const logo="/assets/logo-c.svg";const s="</script>";')
            (dist / 'assets' / 'index-b.css').write_text('.a{background:url(/assets/logo-c.svg)}')
            (dist / 'assets' / 'logo-c.svg').write_text('<svg/>')
            (dist / 'map.png').write_bytes(b'\x89PNG')
            (dist / 'assets' / 'index-a.js').write_text((dist / 'assets' / 'index-a.js').read_text() + 'const m="/map.png";')
            payload = {'version': 'v1', 'stations': {'1': {'역명': '길동역'}}}
            out = static_page.build(Path(tmp) / 'out' / 'index.html', payload, dist)
            html = out.read_text(encoding='utf-8')
            self.assertNotIn('/assets/', html)
            self.assertIn('const m="data:image/png;base64,', html)
            self.assertIn('<style>.a{background:url(data:image/svg+xml;base64,', html)
            self.assertIn('const s="<\\/script>"', html)
            packed = html.split('window.__STATIC_DATA_GZ__="')[1].split('"')[0]
            self.assertEqual(json.loads(gzip.decompress(base64.b64decode(packed))), payload)
            self.assertEqual(out.stat().st_mode & 0o077, 0)
            with self.assertRaises(FileNotFoundError):
                static_page.build(Path(tmp) / 'out2.html', payload, Path(tmp) / 'missing')


if __name__ == '__main__':
    unittest.main()
