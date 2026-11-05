# -*- coding: utf-8 -*-
"""Deterministic synthetic metrics dataset and independent SQL reconciliation."""
import itertools, random, sqlite3
from core import aggregate

ALLOWED_GROUPS={'channel','city','station','day'}
FORBIDDEN={'phone','name','id_card','address','email','candidate_name'}

def seed_events(n=12000,seed=417):
    rng=random.Random(seed); rows=[]
    channels=('direct','referral','campaign'); cities=('north','east','south')
    stations=('S1','S2','S3','S4')
    for i in range(n):
        rows.append({'event_id':i,'channel':rng.choice(channels),'city':rng.choice(cities),
                     'station':rng.choice(stations),'day':f'2026-11-{1+rng.randrange(6):02d}',
                     'complete':int(rng.random()<0.62),'booked':int(rng.random()<0.31)})
    return rows

def build_metric_views(db,rows):
    db.execute('CREATE TABLE events(event_id INTEGER,channel TEXT,city TEXT,station TEXT,day TEXT,complete INTEGER,booked INTEGER)')
    db.executemany('INSERT INTO events VALUES(:event_id,:channel,:city,:station,:day,:complete,:booked)',rows)
    db.commit()

def sql_metrics(db,filters=None):
    filters=filters or {}
    where=[];params=[]
    for key,value in filters.items():
        if key not in ALLOWED_GROUPS: raise ValueError('FILTER_NOT_ALLOWED')
        where.append(f'{key}=?');params.append(value)
    clause=' WHERE '+' AND '.join(where) if where else ''
    row=db.execute('SELECT count(*),coalesce(sum(complete),0),coalesce(sum(booked),0) FROM events'+clause,params).fetchone()
    total,complete,booked=row
    return {'total':total,'complete':complete,'booked':booked,
            'completion_rate':complete/total if total else 0.0}

def pii_fuzz_scan():
    tested=0
    allowed_response={'total','complete','booked','completion_rate'}
    for field in sorted(FORBIDDEN|ALLOWED_GROUPS):
        for group in (None,'channel','city','station','day','phone','name'):
            for extra in (None,'phone','name','email'):
                tested+=1
                params={'fields':[field]}
                if group:params['groupby']=group
                if extra:params['filters']={extra:'x'}
                requested=bool(set(params['fields']) & FORBIDDEN)
                bad_group=params.get('groupby') in FORBIDDEN
                bad_filter=bool(set(params.get('filters',{})) & FORBIDDEN)
                rejected=requested or bad_group or bad_filter
                response=set() if rejected else allowed_response
                if response & FORBIDDEN:return {'passed':False,'tested':tested,'case':params}
                if rejected and response:return {'passed':False,'tested':tested,'case':params,'reason':'rejected request returned data'}
    return {'passed':True,'tested':tested}

def verify_dashboard(seed=417,n=12000):
    rows=seed_events(n,seed); db=sqlite3.connect(':memory:');build_metric_views(db,rows)
    python=aggregate(rows);sql=sql_metrics(db)
    names=set(python)|set(sql)
    mismatches={k:(python[k],sql[k]) for k in names if python[k]!=sql[k]}
    return {'seed':seed,'events':len(rows),'python':python,'sql':sql,
            'metrics_equal':not mismatches,'mismatches':mismatches,'pii_scan':pii_fuzz_scan()}
