# -*- coding: utf-8 -*-
"""Deterministic recruitment workflow helpers; synthetic/local demonstration."""
import hashlib
import hmac
import json
import unicodedata

TRANSITIONS={
    'awaiting_consent': {'collecting','withdrawn'},
    'collecting': {'complete','end_minor','withdrawn'},
    'complete': {'booked','withdrawn'},
    'booked': {'interviewed','withdrawn'},
    'end_minor': {'withdrawn'},
    'interviewed': {'hired','rejected','withdrawn'},
    'new': {'contacted','withdrawn'},
    'contacted': {'registered','withdrawn'},
    'registered': {'scheduled','withdrawn'},
    'scheduled': {'interviewed','withdrawn'},
    'interviewed': {'hired','rejected','withdrawn'},
    'hired': set(), 'rejected': set(), 'withdrawn': set(),
}

def transition(current:str,target:str)->str:
    if current not in TRANSITIONS or target not in TRANSITIONS:
        raise ValueError('TRANSITION_UNKNOWN_STATE')
    if current==target: raise ValueError('TRANSITION_SAME_STATE')
    if target not in TRANSITIONS[current]: raise ValueError('TRANSITION_ILLEGAL')
    return target

def normalize_phone(value:str)->str:
    text=unicodedata.normalize('NFKC',value)
    digits=''.join(str(unicodedata.digit(ch)) for ch in text if ch.isdecimal())
    if digits.startswith('0086'): digits=digits[4:]
    elif digits.startswith('86') and len(digits)==13: digits=digits[2:]
    if len(digits)!=11 or digits[0]!='1' or digits[1] not in '3456789':
        raise ValueError('PHONE_INVALID')
    return digits

def dedupe_key(phone:str,name:str,station:str,secret:bytes)->str:
    norm_name=''.join(unicodedata.normalize('NFKC',name).casefold().split())
    norm_station=''.join(unicodedata.normalize('NFKC',station).casefold().split())
    raw='|'.join((normalize_phone(phone),norm_name,norm_station)).encode()
    return hmac.new(secret,raw,hashlib.sha256).hexdigest()

def sign_event(event_id:str,payload:dict,secret:bytes)->str:
    raw=json.dumps({'event_id':event_id,'payload':payload},sort_keys=True,separators=(',',':')).encode()
    return hmac.new(secret,raw,hashlib.sha256).hexdigest()

def verify_event(event_id:str,payload:dict,signature:str,secret:bytes)->bool:
    return hmac.compare_digest(sign_event(event_id,payload,secret),signature)
