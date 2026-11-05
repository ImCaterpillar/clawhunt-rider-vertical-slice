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

if __name__=='__main__': unittest.main(verbosity=2)
