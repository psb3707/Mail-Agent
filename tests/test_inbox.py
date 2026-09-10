"""Inbound lifecycle, idempotency, atomic storage and NEW acknowledgement."""
from copy import deepcopy
from pathlib import Path
import json
from threading import Event, Thread
from uuid import uuid4

import pytest
from app.inbox import MailboxStore
from app.grouping import reassemble
from app.search import answer_question


def make_store():
    indexed=json.loads(Path('data/indexed.json').read_text(encoding='utf-8'))
    mails=json.loads(Path('data/mails.json').read_text(encoding='utf-8'))['mails']
    return MailboxStore(indexed,mails)


def offline(_):
    raise RuntimeError('offline')


def receive(store,scenario='existing'):
    eid=str(uuid4())
    store.begin(eid,scenario)
    store.process(eid,offline)
    return store.event(eid)


def test_existing_receipt_is_atomic_and_visible_to_summary():
    store=make_store()
    before=store.snapshot()
    result=receive(store)
    assert result['status']=='saved' and result['decision']=='existing'
    assert [s['status'] for s in result['steps']]==['received','classifying','classified','saved']
    current=store.snapshot()
    assert len(current['mails'])==401 and len(before['mails'])==400
    card=next(c for c in reassemble(current) if c['id']=='c-m0001')
    assert len(card['mails'])==7 and card['latest_body']==result['mail']['body']
    answer=answer_question('최근 메일 요약해봐',current,offline)
    assert answer['sources'][0]['id']==result['mail']['id']
    assert store.mark_read(result['mail']['id'])
    assert not next(m for m in store.snapshot()['mails'] if m['id']==result['mail']['id'])['_is_new']
    assert store.mark_read(result['mail']['id'])
    assert not store.mark_read('missing')


def test_new_case_and_alert_have_distinct_destinations():
    store=make_store()
    new=receive(store,'new_case')
    assert new['decision']=='new_case'
    assert len(store.snapshot()['cases'])==10
    again=receive(store,'new_case')
    assert again['decision']=='existing' and again['case_id']==new['case_id']
    assert len(store.snapshot()['cases'])==10
    alert=receive(store,'alert')
    indexed=store.snapshot()
    assert alert['decision']=='non_case' and not alert['case_id']
    assert any(m['id']==alert['mail']['id'] for m in indexed['non_cases'])
    assert all(alert['mail']['id'] not in c['mail_ids'] for c in indexed['cases'])
    assert len(indexed['mails'])==403


def test_duplicate_receive_event_does_not_duplicate_mail_or_call_model():
    store=make_store()
    eid=str(uuid4());calls=[]
    store.begin(eid,'existing')
    def classify(_): calls.append(1); return 'c-m0001'
    store.process(eid,classify)
    store.begin(eid,'existing');store.process(eid,classify)
    assert len(calls)==1 and len(store.snapshot()['mails'])==401
    with pytest.raises(ValueError):store.begin(eid,'alert')


def test_readers_remain_available_during_classification():
    store=make_store();eid=str(uuid4());entered=Event();release=Event()
    store.begin(eid,'existing')
    def slow(_):
        entered.set(); assert release.wait(5);return 'c-m0001'
    worker=Thread(target=store.process,args=(eid,slow))
    worker.start()
    try:
        assert entered.wait(3)
        assert store.event(eid)['status']=='classifying'
        assert len(store.snapshot()['mails'])==400
    finally:
        release.set();worker.join(5)
    assert store.event(eid)['status']=='saved'


def test_invalid_classification_does_not_partially_save(monkeypatch):
    store=make_store();before=store.snapshot();eid=str(uuid4());store.begin(eid,'existing')
    monkeypatch.setattr('app.inbox.grouping.classify_new_mail',lambda *a:{'decision':'existing','case_id':'missing'})
    store.process(eid,offline)
    assert store.event(eid)['status']=='failed'
    assert store.snapshot()==before


def test_store_never_mutates_input():
    idx={'cases':[],'non_cases':[]};mails=[];original=deepcopy(idx)
    store=MailboxStore(idx,mails)
    event=receive(store,'alert')
    assert event['status']=='saved'
    assert idx==original and mails==[]


def test_receive_api_refresh_read_and_validation(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    store=make_store();monkeypatch.setattr('app.main.mailbox',store);monkeypatch.setattr('app.main.llm.llm_call',offline)
    client=TestClient(app);eid=str(uuid4());payload={'event_id':eid,'scenario':'existing'}
    received=client.post('/inbox/receive',json=payload)
    assert received.status_code==202 and received.json()['status']=='received'
    event=client.get('/inbox/events/'+eid).json()
    assert event['status']=='saved'
    mid=event['mail']['id']
    html=client.get('/').text
    assert f'data-new-mail="{mid}"' in html
    assert '계약 서명 완료' in html
    assert client.post('/inbox/receive',json=payload).json()['status']=='saved'
    assert len(store.snapshot()['mails'])==401
    assert client.post('/inbox/mails/'+mid+'/read').status_code==200
    assert f'data-new-mail="{mid}"' not in client.get('/').text
    assert client.get('/inbox/events/'+str(uuid4())).status_code==404
    assert client.post('/inbox/receive',json={'event_id':'bad','scenario':'existing'}).status_code==422
    assert client.post('/inbox/receive',json={'event_id':eid,'scenario':'alert'}).status_code==409
