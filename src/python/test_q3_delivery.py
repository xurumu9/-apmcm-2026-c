"""Release integrity tests with synthetic files; no contest data required."""
import tempfile
import unittest
from pathlib import Path
from q3_delivery import digest,validate_manifest


class DeliveryTests(unittest.TestCase):
    def test_verified_file_then_detect_tampering_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(Path(tmp).resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()))
            p=Path(tmp)/'summary.csv';p.write_text('estimate\n0.5\n',encoding='utf-8')
            manifest={'files':[dict(path=p.name,bytes=p.stat().st_size,sha256=digest(p))]}
            self.assertEqual(validate_manifest(tmp,manifest),[])
            p.write_text('estimate\n0.9\n',encoding='utf-8')
            self.assertTrue(validate_manifest(tmp,manifest)[0].startswith('HASH_MISMATCH'))
            manifest['files'][0]['path']='not-present.csv'
            self.assertTrue(validate_manifest(tmp,manifest)[0].startswith('MISSING'))

    def test_paths_cannot_escape_release_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(Path(tmp).resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()))
            manifest={'files':[dict(path='../outside.csv',bytes=0,sha256='none')]}
            self.assertTrue(validate_manifest(tmp,manifest)[0].startswith('OUTSIDE_ROOT'))


if __name__=='__main__':unittest.main()
