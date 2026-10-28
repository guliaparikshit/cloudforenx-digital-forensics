import unittest
from pathlib import Path
import shutil
from storage import (create_session_store, save_evidence, get_records, get_custody,
                     verify_evidence, add_custody_note, hash_bytes)

class CloudForenXTests(unittest.TestCase):
    def setUp(self):
        self.root = create_session_store()
    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
    def upload(self):
        return save_evidence(self.root,case_id="CASE-101",evidence_name="Sample chat",evidence_type="Document",collected_by="Demo user",filename="sample.txt",data=b"sample evidence content")
    def test_sha256_known_digest(self):
        self.assertEqual(hash_bytes(b"abc"),"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    def test_upload_and_sqlite(self):
        item=self.upload()
        self.assertEqual(item['sha256'],hash_bytes(b"sample evidence content"))
        self.assertEqual(get_records(self.root)[0]['case_id'],'CASE-101')
        self.assertEqual(len(get_custody(self.root)),1)
    def test_match_and_mismatch(self):
        item=self.upload()
        self.assertTrue(verify_evidence(self.root,item['id'],b"sample evidence content","Demo user")[0])
        self.assertFalse(verify_evidence(self.root,item['id'],b"changed","Demo user")[0])
        self.assertEqual(len(get_custody(self.root)),3)
    def test_manual_custody(self):
        item=self.upload()
        add_custody_note(self.root,item['id'],"Reviewer","Viewed record","Test")
        self.assertEqual(get_custody(self.root)[0]['action'],"Viewed record")
    def test_bad_metadata_and_large_file(self):
        with self.assertRaises(ValueError):
            save_evidence(self.root,case_id="",evidence_name="Name",evidence_type="Image",collected_by="Demo",filename="x",data=b"abc")
        with self.assertRaises(ValueError):
            save_evidence(self.root,case_id="CASE",evidence_name="Name",evidence_type="Image",collected_by="Demo",filename="x",data=b"x"*(12*1024*1024+1))

if __name__ == '__main__':
    unittest.main()
