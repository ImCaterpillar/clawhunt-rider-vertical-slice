# -*- coding: utf-8 -*-
import os, tempfile, threading, unittest
from fastapi.testclient import TestClient

class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        os.environ['RIDER_DEMO_DB']=os.path.join(self.tmp.name,'demo.sqlite3')
        import api_app
        api_app.DB_PATH=os.environ['RIDER_DEMO_DB']
        self.module=api_app
        self.client=TestClient(api_app.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None,None,None)
        self.tmp.cleanup()

    def complete_session(self):
        sid=self.client.post('/api/v1/sessions').json()['session_id']
        self.assertEqual(self.client.post(f'/api/v1/sessions/{sid}/consent',json={'version':'test-v1'}).status_code,200)
        a=self.client.post(f'/api/v1/sessions/{sid}/message',json={'text':'name=Lee birth_ym=1995-01 area=Qingdao'})
        self.assertEqual(a.json()['progress'],'3/7')
        b=self.client.post(f'/api/v1/sessions/{sid}/message',json={'text':'job_type=fulltime has_ebike=yes start_date=soon experience=2years'})
        self.assertEqual(b.json()['progress'],'7/7')
        return sid

    def test_consent_gates_message_and_masking(self):
        sid=self.client.post('/api/v1/sessions').json()['session_id']
        r=self.client.post(f'/api/v1/sessions/{sid}/message',json={'text':'name=Lee phone=138-0013-8000'})
        self.assertEqual(r.status_code,403)
        self.client.post(f'/api/v1/sessions/{sid}/consent',json={'version':'v1'})
        r=self.client.post(f'/api/v1/sessions/{sid}/message',json={'text':'name=Lee phone=138-0013-8000'})
        self.assertNotIn('138-0013-8000',r.json()['model_input'])
        self.assertIn('〔手机号_',r.json()['model_input'])

    def test_booking_persists_and_metrics_aggregate_only(self):
        sid=self.complete_session()
        r=self.client.post(f'/api/v1/sessions/{sid}/book',json={})
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.get('/api/v1/metrics').json(),{'total':1,'complete':1,'booked':1})
        self.client.__exit__(None,None,None)
        self.client=TestClient(self.module.app); self.client.__enter__()
        self.assertEqual(self.client.get('/api/v1/metrics').json()['booked'],1)

    def test_atomic_capacity_under_concurrency(self):
        ids=[self.complete_session() for _ in range(10)]
        results=[]; lock=threading.Lock()
        def reserve(sid):
            with TestClient(self.module.app) as c:
                r=c.post(f'/api/v1/sessions/{sid}/book',json={})
                with lock: results.append(r.status_code)
        threads=[threading.Thread(target=reserve,args=(sid,)) for sid in ids]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(results.count(200),5)
        self.assertEqual(results.count(409),5)
        self.assertEqual(self.client.get('/api/v1/metrics').json()['booked'],5)

    def test_revoke_deletes_session_and_booking(self):
        sid=self.complete_session(); self.assertEqual(self.client.post(f'/api/v1/sessions/{sid}/book',json={}).status_code,200)
        self.assertEqual(self.client.delete(f'/api/v1/sessions/{sid}/consent').json()['status'],'deleted')
        self.assertEqual(self.client.get('/api/v1/metrics').json()['total'],0)
        self.assertEqual(self.client.get('/api/v1/metrics').json()['booked'],0)
        self.assertTrue(self.client.get('/api/v1/audit/verify').json()['valid'])

    def test_persistent_audit_chain_detects_tamper(self):
        sid=self.complete_session()
        self.client.post(f'/api/v1/sessions/{sid}/book',json={})
        self.assertTrue(self.client.get('/api/v1/audit/verify').json()['valid'])
        with self.module.conn() as c: c.execute("UPDATE audit SET event='tampered' WHERE seq=1")
        result=self.client.get('/api/v1/audit/verify').json()
        self.assertFalse(result['valid']); self.assertEqual(result['seq'],1)

    def test_lead_dedup_normalizes_variants_and_stores_tokens(self):
        a=self.client.post('/api/v1/leads',json={'phone':'13800138000','name':'张 三','station':'站点 A'})
        b=self.client.post('/api/v1/leads',json={'phone':'＋８６（１３８）００１３－８０００','name':' 张三 ','station':'站点A'})
        self.assertTrue(a.json()['created']); self.assertFalse(b.json()['created'])
        with self.module.conn() as c:
            row=c.execute('SELECT * FROM leads').fetchone()
            self.assertNotIn('13800138000',str(dict(row)))
            self.assertNotIn('张三',str(dict(row)))

    def test_webhook_outbox_idempotency_signature_and_tampering(self):
        body={'event_id':'evt-1','payload':{'type':'candidate.scheduled','candidate_token':'tok-1'}}
        first=self.client.post('/api/v1/outbox',json=body).json()
        second=self.client.post('/api/v1/outbox',json=body).json()
        self.assertTrue(first['created']); self.assertFalse(second['created'])
        conflict=self.client.post('/api/v1/outbox',json={'event_id':'evt-1','payload':{'type':'candidate.hired'}})
        self.assertEqual(conflict.status_code,409)
        valid=self.client.post('/api/v1/outbox/verify',json={**body,'signature':first['signature']}).json()
        bad=self.client.post('/api/v1/outbox/verify',json={**body,'payload':{'type':'candidate.hired','candidate_token':'tok-1'},'signature':first['signature']}).json()
        self.assertTrue(valid['valid']); self.assertFalse(bad['valid'])
        stored=self.client.get('/api/v1/outbox/evt-1').json()
        self.assertEqual(stored['payload'],body['payload'])

    def test_session_state_machine_rejects_illegal_transition_and_bypass(self):
        sid=self.client.post('/api/v1/sessions').json()['session_id']
        bad=self.client.post(f'/api/v1/sessions/{sid}/status',json={'status':'hired'})
        self.assertEqual(bad.status_code,403)
        self.assertEqual(bad.json()['detail'],'CONSENT_REQUIRED')
        self.client.post(f'/api/v1/sessions/{sid}/consent',json={'version':'test-v1'})
        bypass=self.client.post(f'/api/v1/sessions/{sid}/status',json={'status':'collecting'})
        self.assertEqual(bypass.status_code,422)
        self.assertEqual(bypass.json()['detail'],'STATUS_TRANSITION_REQUIRES_DEDICATED_ENDPOINT')
        illegal=self.client.post(f'/api/v1/sessions/{sid}/status',json={'status':'hired'})
        self.assertEqual(illegal.status_code,422)
        self.assertEqual(illegal.json()['detail'],'TRANSITION_ILLEGAL')

if __name__=='__main__': unittest.main(verbosity=2)
