# -*- coding: utf-8 -*-
"""Deterministic synthetic metrics dataset and independent SQL reconciliation."""
import itertools, random, sqlite3
from core import aggregate

ALLOWED_GROUPS={'channel','city','station','day'}
ALLOWED_METRICS={'total','complete','booked','completion_rate'}
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


def query_metrics(db,fields=None,groupby=None,filters=None):
    fields=set(fields or ALLOWED_METRICS)
    filters=filters or {}
    if not fields or not fields<=ALLOWED_METRICS: raise ValueError('FIELD_NOT_ALLOWED')
    if groupby is not None and groupby not in ALLOWED_GROUPS: raise ValueError('GROUP_NOT_ALLOWED')
    where=[];params=[]
    for key,value in filters.items():
        if key not in ALLOWED_GROUPS: raise ValueError('FILTER_NOT_ALLOWED')
        where.append(f'{key}=?');params.append(value)
    clause=' WHERE '+' AND '.join(where) if where else ''
    row=db.execute('SELECT count(*),coalesce(sum(complete),0),coalesce(sum(booked),0) FROM events'+clause,params).fetchone()
    total,complete,booked=row
    full={'total':total,'complete':complete,'booked':booked,
          'completion_rate':complete/total if total else 0.0}
    return {key:full[key] for key in sorted(fields)}


def sql_metrics(db,filters=None):
    return query_metrics(db,filters=filters)


def pii_fuzz_scan():
    db=sqlite3.connect(':memory:');build_metric_views(db,seed_events(120,31))
    tested=0; rejected=0
    field_cases=[('total',),('phone',),('name',),('id_card',),('address',),('email',),('candidate_name',)]
    group_cases=(None,'channel','city','station','day','phone','name')
    filter_cases=(None,{}, {'channel':'direct'}, {'phone':'13800138000'},
                  {'name':'sample'}, {'email':'a@example.invalid'})
    for fields,group,filters in itertools.product(field_cases,group_cases,filter_cases):
        tested+=1
        try:
            result=query_metrics(db,fields=fields,groupby=group,filters=filters)
        except ValueError:
            rejected+=1
            continue
        if set(result)&FORBIDDEN or not set(result)<=ALLOWED_METRICS:
            return {'passed':False,'tested':tested,'rejected':rejected,
                    'case':{'fields':fields,'groupby':group,'filters':filters},'result':result}
    expected_rejections=tested-1*5*3
    return {'passed':rejected==expected_rejections,'tested':tested,'rejected':rejected,
            'expected_rejections':expected_rejections}


def verify_dashboard(seed=417,n=12000):
    rows=seed_events(n,seed); db=sqlite3.connect(':memory:');build_metric_views(db,rows)
    python=aggregate(rows);sql=sql_metrics(db)
    names=set(python)|set(sql)
    mismatches={k:(python[k],sql[k]) for k in names if python[k]!=sql[k]}
    return {'seed':seed,'events':len(rows),'python':python,'sql':sql,
            'metrics_equal':not mismatches,'mismatches':mismatches,'pii_scan':pii_fuzz_scan()}
