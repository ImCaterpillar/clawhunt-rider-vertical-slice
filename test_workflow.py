# -*- coding: utf-8 -*-
import itertools, unittest
from workflow import TRANSITIONS, dedupe_key, normalize_phone, sign_event, transition, verify_event
from core import mask_and_tokenize

class WorkflowTests(unittest.TestCase):
    def test_every_state_pair_has_explicit_result(self):
        for source,target in itertools.product(TRANSITIONS,repeat=2):
            if source==target:
                with self.assertRaisesRegex(ValueError,'TRANSITION_SAME_STATE'): transition(source,target)
            elif target in TRANSITIONS[source]:
                self.assertEqual(transition(source,target),target)
            else:
                with self.assertRaisesRegex(ValueError,'TRANSITION_ILLEGAL'): transition(source,target)

    def test_unknown_state_rejected(self):
        with self.assertRaisesRegex(ValueError,'TRANSITION_UNKNOWN_STATE'): transition('new','teleported')

    def test_phone_variants_normalize_identically(self):
        variants=['13800138000','+86 138-0013-8000','＋８６（１３８）００１３－８０００','138\u200b0013\u200d8000']
        self.assertEqual({normalize_phone(v) for v in variants},{'13800138000'})
        keys={dedupe_key(v,' 张 三 ','站点 A',b'fixture-key') for v in variants}
        self.assertEqual(len(keys),1)

    def test_invalid_phone_rejected(self):
        for value in ('23800138000','1380013800','138001380000'):
            with self.assertRaises(ValueError): normalize_phone(value)

    def test_event_signature_is_bound_to_payload_and_id(self):
        secret=b'test-secret'; payload={'status':'scheduled','candidate':'token-1'}
        sig=sign_event('event-1',payload,secret)
        self.assertTrue(verify_event('event-1',payload,sig,secret))
        self.assertFalse(verify_event('event-2',payload,sig,secret))
        self.assertFalse(verify_event('event-1',{**payload,'status':'hired'},sig,secret))

    def test_phone_masking_covers_unicode_and_zero_width(self):
        cases=['138-0013-8000','＋８６ １３８－００１３－８０００','138\u200b0013\u200d8000']
        for raw in cases:
            safe,tokens=mask_and_tokenize('contact='+raw,b'mask-key')
            self.assertNotIn('138',safe)
            self.assertEqual(list(tokens.values()),['13800138000'])

if __name__=='__main__': unittest.main(verbosity=2)
