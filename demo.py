# -*- coding: utf-8 -*-
"""Local mock vertical slice; no real PII, external services, or production claims."""
import json
from core import AuditChain, Capacity, Session, aggregate

s=Session(); s.give_consent("demo-consent-v1")
for message in ("name=Chen birth_ym=1998-05 area=Haidian",
                "job_type=fulltime has_ebike=yes start_date=within-7-days experience=2-years"):
    s.accept_message(message,b"demo-only-not-production")
capacity=Capacity(2); booked=capacity.book("candidate-demo-1")
audit=AuditChain(); audit.append("consent","candidate-token-demo"); audit.append("booking","candidate-token-demo")
metrics=aggregate([{"complete":True,"booked":booked},{"complete":False,"booked":False}])
print(json.dumps({"demo_only":True,"status":s.status,"progress":s.progress,
                  "appointment_booked":booked,"remaining_capacity":capacity.remaining,
                  "audit_chain_valid":audit.verify(),"aggregate_metrics":metrics},indent=2))
