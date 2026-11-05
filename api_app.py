# -*- coding: utf-8 -*-
"""Local SQLite-backed API demo. Not production-ready; synthetic data only."""
from __future__ import annotations
import json, os, re, sqlite3, uuid
from contextlib import asynccontextmanager, contextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from core import SLOTS, mask_and_tokenize

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
            seq INTEGER PRIMARY KEY AUTOINCREMENT,event TEXT NOT NULL,subject_token TEXT NOT NULL)''')
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

@app.post('/api/v1/sessions')
def create_session():
    sid=uuid.uuid4().hex
    with conn() as c: c.execute('INSERT INTO sessions VALUES(?,?,?,?,?)',(sid,None,'awaiting_consent','{}','{}'))
    return {'session_id':sid,'status':'awaiting_consent'}

@app.post('/api/v1/sessions/{sid}/consent')
def give_consent(sid:str,body:Consent):
    with conn() as c:
        cur=c.execute("UPDATE sessions SET consent_version=?,status='collecting' WHERE id=?",(body.version,sid))
        if cur.rowcount!=1: raise HTTPException(404,'SESSION_NOT_FOUND')
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
        c.execute('UPDATE sessions SET slots_json=?,token_map_json=?,status=? WHERE id=?',
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
            c.execute('INSERT INTO audit(event,subject_token) VALUES(?,?)',('booking',sid[:12]))
            c.execute('COMMIT')
            return {'booking_id':booking_id,'status':'booked','remaining':capacity['remaining']-1}
        except HTTPException:
            c.execute('ROLLBACK'); raise
        except sqlite3.IntegrityError:
            c.execute('ROLLBACK'); raise HTTPException(409,'DUPLICATE_BOOKING')
        except Exception:
            c.execute('ROLLBACK'); raise

@app.get('/api/v1/metrics')
def metrics():
    with conn() as c:
        total=c.execute('SELECT count(*) FROM sessions').fetchone()[0]
        complete=c.execute("SELECT count(*) FROM sessions WHERE status='complete'").fetchone()[0]
        booked=c.execute('SELECT count(*) FROM bookings').fetchone()[0]
    return {'total':total,'complete':complete,'booked':booked}

@app.delete('/api/v1/sessions/{sid}/consent')
def revoke(sid:str):
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        try:
            row=c.execute('SELECT id FROM sessions WHERE id=?',(sid,)).fetchone()
            if not row: raise HTTPException(404,'SESSION_NOT_FOUND')
            c.execute("INSERT INTO audit(event,subject_token) VALUES('consent_revoked',?)",(sid[:12],))
            c.execute('DELETE FROM bookings WHERE session_id=?',(sid,))
            c.execute('DELETE FROM sessions WHERE id=?',(sid,))
            c.execute('COMMIT')
        except HTTPException:
            c.execute('ROLLBACK'); raise
        except Exception:
            c.execute('ROLLBACK'); raise
    return {'status':'deleted'}
