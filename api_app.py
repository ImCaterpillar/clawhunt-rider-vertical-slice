# -*- coding: utf-8 -*-
"""Local SQLite-backed API demo. Not production-ready; synthetic data only."""
from __future__ import annotations
import hashlib, hmac, json, os, re, sqlite3, uuid
from contextlib import asynccontextmanager, contextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from core import SLOTS, mask_and_tokenize
from workflow import transition, dedupe_key, sign_event, normalize_phone

DB_PATH=os.environ.get('RIDER_DEMO_DB','rider_demo.sqlite3')
SECRET=b'demo-only-not-production'
@asynccontextmanager
async def lifespan(app):
    with conn() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.execute('''CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, consent_version TEXT, status TEXT NOT NULL,
            slots_json TEXT NOT NULL, token_map_json TEXT NOT NULL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS capacity (
            station TEXT PRIMARY KEY, remaining INTEGER NOT NULL CHECK(remaining>=0))''')
        c.execute('''CREATE TABLE IF NOT EXISTS bookings (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, station TEXT NOT NULL,
            UNIQUE(session_id,station))''')
        c.execute('''CREATE TABLE IF NOT EXISTS audit (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,event TEXT NOT NULL,subject_token TEXT NOT NULL,
            prev_hash TEXT NOT NULL DEFAULT '',entry_hash TEXT NOT NULL DEFAULT '')''')
        audit_cols={row['name'] for row in c.execute('PRAGMA table_info(audit)')}
        if 'prev_hash' not in audit_cols: c.execute("ALTER TABLE audit ADD COLUMN prev_hash TEXT NOT NULL DEFAULT ''")
        if 'entry_hash' not in audit_cols: c.execute("ALTER TABLE audit ADD COLUMN entry_hash TEXT NOT NULL DEFAULT ''")
        c.execute('''CREATE TABLE IF NOT EXISTS leads (
            dedupe_key TEXT PRIMARY KEY,name_token TEXT NOT NULL,station TEXT NOT NULL,
            phone_token TEXT NOT NULL,status TEXT NOT NULL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS outbox (
            event_id TEXT PRIMARY KEY,event_type TEXT NOT NULL,payload_json TEXT NOT NULL,
            signature TEXT NOT NULL,delivered INTEGER NOT NULL DEFAULT 0)''')
        c.execute("INSERT OR IGNORE INTO capacity(station,remaining) VALUES('demo-station',5)")
    yield

app=FastAPI(title='Rider Vertical Slice Demo',version='0.2.0',lifespan=lifespan)

@contextmanager
def conn():
    c=sqlite3.connect(DB_PATH,timeout=10,isolation_level=None)
    c.row_factory=sqlite3.Row
    try:
        yield c
    finally: c.close()

class Consent(BaseModel): version:str
class Message(BaseModel): text:str
class Booking(BaseModel): station:str='demo-station'
class Lead(BaseModel): phone:str; name:str; station:str; status:str='new'
class StateChange(BaseModel): status:str
class EventRequest(BaseModel): event_id:str; payload:dict; signature:str=''
class LeadState(BaseModel): status:str


def append_audit(c, event:str, subject_token:str):
    previous=c.execute('SELECT entry_hash FROM audit ORDER BY seq DESC LIMIT 1').fetchone()
    prev_hash=previous['entry_hash'] if previous else '0'*64
    body={'event':event,'subject_token':subject_token,'prev_hash':prev_hash}
    entry_hash=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    c.execute('INSERT INTO audit(event,subject_token,prev_hash,entry_hash) VALUES(?,?,?,?)',
              (event,subject_token,prev_hash,entry_hash))

@app.post('/api/v1/sessions')
def create_session():
    sid=uuid.uuid4().hex
    with conn() as c: c.execute('INSERT INTO sessions VALUES(?,?,?,?,?)',(sid,None,'awaiting_consent','{}','{}'))
    return {'session_id':sid,'status':'awaiting_consent'}

@app.post('/api/v1/sessions/{sid}/consent')
def give_consent(sid:str,body:Consent):
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        cur=c.execute("UPDATE sessions SET consent_version=?,status='collecting' WHERE id=? AND status='awaiting_consent'",(body.version,sid))
        if cur.rowcount!=1:
            exists=c.execute('SELECT 1 FROM sessions WHERE id=?',(sid,)).fetchone()
            c.execute('ROLLBACK')
            if not exists: raise HTTPException(404,'SESSION_NOT_FOUND')
            raise HTTPException(409,'CONSENT_ALREADY_SET_OR_SESSION_CLOSED')
        append_audit(c,'consent_given',sid[:12])
        c.execute('COMMIT')
    return {'status':'collecting','consent_version':body.version}

@app.post('/api/v1/sessions/{sid}/message')
def message(sid:str,body:Message):
    safe,tokens=mask_and_tokenize(body.text,SECRET)
    with conn() as c:
        row=c.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone()
        if not row: raise HTTPException(404,'SESSION_NOT_FOUND')
        if row['status']!='collecting': raise HTTPException(403,'CONSENT_REQUIRED')
        slots=json.loads(row['slots_json']); token_map=json.loads(row['token_map_json']); token_map.update(tokens)
        for slot in SLOTS:
            m=re.search(r'(?:^|\s)'+re.escape(slot)+r'=([^\s;]+)',safe)
            if m: slots[slot]=m.group(1)
        status='collecting'
        if slots.get('birth_ym','').startswith(('2008','2009','2010')):
            status='end_minor'; slots={}; token_map={}
        elif len(slots)==len(SLOTS): status='complete'
        c.execute('UPDATE sessions SET slots_json=?,token_map_json=?,status=? WHERE id=? AND status=\'collecting\'',
                  (json.dumps(slots),json.dumps(token_map),status,sid))
    return {'status':status,'progress':f'{len(slots)}/{len(SLOTS)}','model_input':safe}

@app.post('/api/v1/sessions/{sid}/book')
def book(sid:str,body:Booking):
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        try:
            row=c.execute('SELECT status FROM sessions WHERE id=?',(sid,)).fetchone()
            if not row: raise HTTPException(404,'SESSION_NOT_FOUND')
            if row['status']!='complete': raise HTTPException(409,'REGISTRATION_INCOMPLETE')
            capacity=c.execute('SELECT remaining FROM capacity WHERE station=?',(body.station,)).fetchone()
            if not capacity or capacity['remaining']<=0: raise HTTPException(409,'NO_CAPACITY')
            c.execute('UPDATE capacity SET remaining=remaining-1 WHERE station=?',(body.station,))
            booking_id=uuid.uuid4().hex
            c.execute('INSERT INTO bookings VALUES(?,?,?)',(booking_id,sid,body.station))
            transition('complete','booked')
            c.execute("UPDATE sessions SET status='booked' WHERE id=?",(sid,))
            append_audit(c,'booking',sid[:12])
            payload={'type':'booking_created','session_id':sid[:12],'station':body.station}
            event_id='booking:'+booking_id
            signature=sign_event(event_id,payload,SECRET)
            c.execute('INSERT INTO outbox(event_id,event_type,payload_json,signature) VALUES(?,?,?,?)',
                      (event_id,payload['type'],json.dumps(payload,sort_keys=True),signature))
            c.execute('COMMIT')
            return {'booking_id':booking_id,'status':'booked','remaining':capacity['remaining']-1}
        except HTTPException:
            c.execute('ROLLBACK'); raise
        except sqlite3.IntegrityError:
            c.execute('ROLLBACK'); raise HTTPException(409,'DUPLICATE_BOOKING')
        except Exception:
            c.execute('ROLLBACK'); raise

@app.post('/api/v1/sessions/{sid}/status')
def change_status(sid:str,body:StateChange):
    if body.status not in ('withdrawn','interviewed','hired','rejected'):
        raise HTTPException(422,'STATUS_TRANSITION_REQUIRES_DEDICATED_ENDPOINT')
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        try:
            row=c.execute('SELECT status,consent_version FROM sessions WHERE id=?',(sid,)).fetchone()
            if not row: raise HTTPException(404,'SESSION_NOT_FOUND')
            if row['status']!='withdrawn' and not row['consent_version']:
                raise HTTPException(403,'CONSENT_REQUIRED')
            try: target=transition(row['status'],body.status)
            except ValueError as e: raise HTTPException(422,str(e))
            c.execute('UPDATE sessions SET status=? WHERE id=?',(target,sid))
            append_audit(c,'status:'+target,sid[:12])
            c.execute('COMMIT')
            return {'session_id':sid,'status':target}
        except HTTPException:
            c.execute('ROLLBACK'); raise
        except Exception:
            c.execute('ROLLBACK'); raise

@app.post('/api/v1/leads')
def create_lead(body:Lead):
    key=dedupe_key(body.phone,body.name,body.station,SECRET)
    normalized_phone=normalize_phone(body.phone)
    phone_token=hmac.new(SECRET,normalized_phone.encode(),hashlib.sha256).hexdigest()
    name_token=hmac.new(SECRET,body.name.encode(),hashlib.sha256).hexdigest()
    with conn() as c:
        cur=c.execute('INSERT OR IGNORE INTO leads VALUES(?,?,?,?,?)',
                      (key,name_token,body.station,phone_token,body.status))
        return {'created':cur.rowcount==1,'dedupe_key':key[:16]}

@app.post('/api/v1/outbox')
def create_event(body:EventRequest):
    signature=sign_event(body.event_id,body.payload,SECRET)
    payload_json=json.dumps(body.payload,sort_keys=True)
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        try:
            row=c.execute('SELECT payload_json,signature FROM outbox WHERE event_id=?',(body.event_id,)).fetchone()
            if row:
                if row['payload_json']!=payload_json:
                    raise HTTPException(409,'EVENT_ID_PAYLOAD_CONFLICT')
                c.execute('COMMIT')
                return {'created':False,'event_id':body.event_id,'signature':row['signature']}
            c.execute('INSERT INTO outbox(event_id,event_type,payload_json,signature) VALUES(?,?,?,?)',
                      (body.event_id,body.payload.get('type','status_changed'),payload_json,signature))
            c.execute('COMMIT')
            return {'created':True,'event_id':body.event_id,'signature':signature}
        except HTTPException:
            c.execute('ROLLBACK'); raise
        except Exception:
            c.execute('ROLLBACK'); raise

@app.post('/api/v1/outbox/verify')
def verify_outbox(body:EventRequest):
    expected=sign_event(body.event_id,body.payload,SECRET)
    valid=hmac.compare_digest(expected,body.signature)
    with conn() as c:
        stored=c.execute('SELECT payload_json,signature FROM outbox WHERE event_id=?',(body.event_id,)).fetchone()
    if stored:
        valid=valid and stored['payload_json']==json.dumps(body.payload,sort_keys=True) and hmac.compare_digest(stored['signature'],body.signature)
    return {'valid':valid,'stored':bool(stored)}

@app.get('/api/v1/outbox/{event_id}')
def read_outbox(event_id:str):
    with conn() as c:
        row=c.execute('SELECT * FROM outbox WHERE event_id=?',(event_id,)).fetchone()
    if not row: raise HTTPException(404,'EVENT_NOT_FOUND')
    return {'event_id':row['event_id'],'event_type':row['event_type'],
            'payload':json.loads(row['payload_json']),'signature':row['signature'],
            'delivered':bool(row['delivered'])}

@app.get('/api/v1/audit/verify')
def verify_audit():
    previous='0'*64
    with conn() as c:
        rows=c.execute('SELECT * FROM audit ORDER BY seq').fetchall()
        for row in rows:
            body={'event':row['event'],'subject_token':row['subject_token'],'prev_hash':row['prev_hash']}
            digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if row['prev_hash']!=previous or not hmac.compare_digest(digest,row['entry_hash']):
                return {'valid':False,'seq':row['seq']}
            previous=row['entry_hash']
    return {'valid':True,'count':len(rows)}

@app.get('/api/v1/metrics')
def metrics():
    with conn() as c:
        total=c.execute('SELECT count(*) FROM sessions').fetchone()[0]
        complete=c.execute("SELECT count(*) FROM sessions WHERE status IN ('complete','booked','interviewed','hired')").fetchone()[0]
        booked=c.execute('SELECT count(*) FROM bookings').fetchone()[0]
    return {'total':total,'complete':complete,'booked':booked}

@app.delete('/api/v1/sessions/{sid}/consent')
def revoke(sid:str):
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        try:
            row=c.execute('SELECT id FROM sessions WHERE id=?',(sid,)).fetchone()
            if not row: raise HTTPException(404,'SESSION_NOT_FOUND')
            append_audit(c,'consent_revoked',sid[:12])
            c.execute('DELETE FROM bookings WHERE session_id=?',(sid,))
            c.execute('DELETE FROM sessions WHERE id=?',(sid,))
            c.execute('COMMIT')
        except HTTPException:
            c.execute('ROLLBACK'); raise
        except Exception:
            c.execute('ROLLBACK'); raise
    return {'status':'deleted'}
