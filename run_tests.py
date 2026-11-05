# -*- coding: utf-8 -*-
import concurrent.futures
import sys
import unittest
sys.path.insert(0, __import__('os').path.dirname(__file__))
from core import AuditChain, Capacity, Session, aggregate, mask_and_tokenize

SECRET=b"demo-only-not-production"

class VerticalSliceTests(unittest.TestCase):
    def test_consent_gate(self):
        s=Session()
        with self.assertRaises(PermissionError): s.accept_message("name=Li", SECRET)
        s.give_consent("v1")
        self.assertEqual(s.status,"collecting")

    def test_pii_masked_before_processing(self):
        safe, mapping=mask_and_tokenize("电话 138-0013-8000", SECRET)
        self.assertNotIn("138-0013-8000",safe)
        self.assertEqual(len(mapping),1)
        self.assertEqual(list(mapping.values()),["13800138000"])

    def test_seven_slot_progress(self):
        s=Session(); s.give_consent("v1")
        s.accept_message("name=Chen birth_ym=1998-05 area=Haiding",SECRET)
        self.assertEqual(s.progress,"3/7")
        s.accept_message("job_type=fulltime has_ebike=yes start_date=soon experience=2years",SECRET)
        self.assertEqual(s.progress,"7/7")
        self.assertEqual(s.status,"complete")

    def test_minor_terminates_and_clears(self):
        s=Session(); s.give_consent("v1")
        s.accept_message("name=Li birth_ym=2008-05",SECRET)
        self.assertEqual(s.status,"end_minor")
        self.assertEqual(s.slots,{})

    def test_revoke_clears_local_data(self):
        s=Session(); s.give_consent("v1"); s.accept_message("name=Li",SECRET); s.revoke()
        self.assertEqual((s.status,s.slots,s.pii_tokens,s.consent_version),("deleted",{},{},None))

    def test_capacity_fifty_compete_for_five(self):
        cap=Capacity(5)
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
            results=list(pool.map(lambda i: cap.book(f"candidate-{i}"),range(50)))
        self.assertEqual(sum(results),5)
        self.assertEqual(cap.remaining,0)

    def test_duplicate_booking_rejected(self):
        cap=Capacity(2)
        self.assertTrue(cap.book("same")); self.assertFalse(cap.book("same")); self.assertEqual(cap.remaining,1)

    def test_audit_chain_detects_tampering(self):
        a=AuditChain(); a.append("consent","subj-1"); a.append("delete","subj-1")
        self.assertTrue(a.verify()); a.rows[0]["event"]="tampered"; self.assertFalse(a.verify())

    def test_aggregate_has_no_pii_fields(self):
        result=aggregate([{"complete":True,"booked":False,"phone":"13800138000","name":"Li"}])
        self.assertEqual(result["completion_rate"],1.0)
        self.assertNotIn("phone",result); self.assertNotIn("name",result)

if __name__=="__main__": unittest.main(verbosity=2)
