"""Synthetic checks of tool semantics, not a replay of dataset samples."""
import json,sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0,str(Path('train+public_test/train+public_test/train').resolve()))
from zaic_tools.apps.bill_payment import BillPayment
from zaic_tools.apps.calendar import Calendar
from zaic_tools.apps.home_security import HomeSecurity
from zaic_tools.apps.package_tracking import PackageTracking
from zaic_tools.apps.tv import Tv
from zaic_tools.apps.smart_home import SmartHome
from zaic_tools.utils import state_hash

checks={}
s=SimpleNamespace(states={'ewallet':{'balance':10}},now='2026-11-03T09:00:00+07:00')
state={'bills':[{'id':'b','amount':20,'paid':False}]}
a=BillPayment(s,state)
assert a.pay('b','ewallet')['done'] is False
assert s.states['ewallet']['balance']==10 and state['bills'][0]['paid'] is False
checks['billpay_insufficient_wallet_has_no_partial_payment']=True
a.schedule_autopay('water',True)
assert state['bills'][0]['paid'] is False
checks['autopay_does_not_pay_existing_bill']=True
before=deepcopy(s.states)
assert a.pay('b','bank')['bill']['paid'] is True and s.states==before
checks['bank_billpay_marks_bill_without_selectable_bank_account']=True
c=Calendar(s,{'events':[{'id':'e','start':'2026-11-04T14:00:00+07:00','status':'cancelled'}]})
assert c.update_event('e',start='2026-11-04T14:00:00+07:00')['item']['status']=='cancelled'
checks['calendar_update_does_not_restore_cancelled_status']=True
h=HomeSecurity(s,{'alerts':[{'id':'a','time':'2026-11-03T08:42:00+07:00'}],'cameras':[{'id':'c','location':'gate','name':'gate','online':False}]})
assert len(h.list_alerts()['alerts'])==1 and h.list_alerts(since=s.now)['alerts']==[]
assert h.get_camera(location='gate home')['cameras']==[] and len(h.get_camera(location='gate')['cameras'])==1
checks['since_now_excludes_earlier_alerts']=True
checks['location_substring_is_not_semantic_alias']=True
p=PackageTracking(s,{'shipments':[{'id':'s','tracking_id':'X'}]})
assert len(p.track()['shipments'])==1 and p.track(tracking_id='None')['shipments']==[]
checks['string_None_is_not_omitted_tracking_id']=True
t=Tv(s,{'power':'on','volume':3})
assert t.control(action='volume',volume=5)['volume']==5
checks['tv_volume_is_absolute_can_increase_instead_of_decrease']=True
sm=SmartHome(s,{'devices':[{'id':'ac','type':'climate','state':{'mode':'off','temperature':24}}]})
assert sm.climate_set('ac',mode='cool')['item']['state']['temperature']==24
assert sm.climate_set('ac',mode='cool',temperature=26)['item']['state']['temperature']==26
checks['omitted_temperature_preserves_existing_value']=True
base={'alarm':{'alarms':[{'id':'a','time':s.now}]},'tasks':{'tasks':[{'id':'t','priority':'normal'}]}}
extra=deepcopy(base);extra['alarm']['alarms'][0]['label']='Added metadata'
assert state_hash(base)==state_hash(extra)
extra['tasks']['tasks'][0]['priority']='high'
assert state_hash(base)!=state_hash(extra)
checks['canon_ignores_label_but_preserves_priority']=True
result={'synthetic_runtime_checks':checks,'passed':len(checks),'dataset_replayed':False,'llm_called':False}
Path('review_data/priority_six_investigation_20261103/runtime_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
