"""In-memory inbound events and atomic mailbox updates for presentation demos."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from threading import RLock, Lock

from app import grouping

SCENARIOS = {
    "existing": {"subject": "〔Project N_CX〕계약 서명 완료 및 킥오프 일정 안내",
                 "sender_name": "김도현", "sender_email": "dohyun.kim@example.com", "sender_dept": "디지털전략팀",
                 "body": "N_CX UI/UX 외주 계약 서명을 완료했습니다. 디자인랩스와 킥오프 일정을 조율하고 있어요. 담당자별 참석 가능 시간을 회신 부탁드립니다.", "reply_to": "m0006"},
    "new_case": {"subject": "〔AURORA〕상담 품질 분석 프로젝트 착수 요청",
                 "sender_name": "정하늘", "sender_email": "haneul.jeong@example.com", "sender_dept": "고객경험팀",
                 "body": "새로운 AURORA 상담 품질 분석 프로젝트를 시작합니다. 상담 품질 분석 범위와 담당자를 정하는 첫 회의를 준비해 주세요. 상담 품질 분석을 위한 별도 업무입니다.", "reply_to": None},
    "alert": {"subject": "〔보안시스템〕오늘의 PC 보안점검 완료 안내",
              "sender_name": "보안시스템", "sender_email": "security@example.com", "sender_dept": "시스템",
              "body": "PC 보안점검이 정상 완료되었습니다. 추가 조치는 필요하지 않습니다. 이 메일은 시스템 자동발송 알림입니다.", "reply_to": None},
}


def _now():
    return datetime.now(timezone.utc).isoformat()


class MailboxStore:
    def __init__(self, indexed, mails):
        self._indexed = deepcopy(indexed)
        self._indexed['mails'] = deepcopy(mails)
        self._events = {}
        self._lock = RLock()
        self._processing = Lock()
        self.revision = 0

    def snapshot(self):
        with self._lock:
            return deepcopy(self._indexed)

    def event(self, event_id):
        with self._lock:
            return deepcopy(self._events.get(event_id))

    def latest_event(self):
        with self._lock:
            return deepcopy(next(reversed(self._events.values()), None))

    def begin(self, event_id, scenario):
        with self._lock:
            if event_id in self._events:
                if self._events[event_id]['scenario'] != scenario:
                    raise ValueError('같은 수신 이벤트 ID에 다른 시나리오를 사용할 수 없어요.')
                return deepcopy(self._events[event_id])
            if scenario not in SCENARIOS:
                raise ValueError('지원하지 않는 수신 시나리오예요.')
            mail = deepcopy(SCENARIOS[scenario])
            mail.update(id='m-inbound-' + event_id,
                        sent_at=datetime.now(timezone(timedelta(hours=9))).replace(tzinfo=None).isoformat(),
                        recipients=['demo@example.com'], attachments=[], _is_new=True)
            event = {'id': event_id, 'scenario': scenario, 'mail': mail,
                     'status': 'received', 'steps': [{'status': 'received', 'at': _now()}]}
            self._events[event_id] = event
            return deepcopy(event)

    def _stage(self, event_id, status, **fields):
        with self._lock:
            event = self._events[event_id]
            event.update(status=status, **fields)
            event['steps'].append({'status': status, 'at': _now()})

    def process(self, event_id, llm_call):
        # Serialize inbound classification against the latest committed snapshot.
        # Readers and status polling remain available while the model is running.
        with self._processing:
            event = self.event(event_id)
            if not event or event['status'] != 'received':
                return
            self._stage(event_id, 'classifying')
            try:
                snapshot = self.snapshot()
                mail = event['mail']
                result = grouping.classify_new_mail(mail, snapshot, llm_call)
                decision, cid = result['decision'], result.get('case_id', '')
                cases = snapshot['cases']
                if decision == 'existing':
                    case = next((c for c in cases if c['id'] == cid), None)
                    if case is None:
                        raise ValueError('분류 결과의 업무가 없습니다.')
                elif decision == 'new_case':
                    key = grouping._norm_subject(mail['subject']) + '|' + mail['sender_dept']
                    cid = 'c-inbound-' + sha256(key.encode()).hexdigest()[:16]
                    case = next((c for c in cases if c['id'] == cid), None)
                    if case is None:
                        case = {'id': cid, 'title': mail['subject'], 'mail_ids': [], 'attachment_ids': [],
                                'period': [], 'mail_type': '프로젝트', 'summary': mail['body']}
                        cases.append(case)
                    else:
                        decision = 'existing'
                elif decision == 'non_case':
                    case = None
                    cid = ''
                else:
                    raise ValueError('분류 결과를 확인할 수 없습니다.')
                destination = case['title'] if case else '반복 알림'
                self._stage(event_id, 'classified', decision=decision, case_id=cid, destination=destination)
                mail = {**mail, '_assigned_case': cid, '_decision': decision}
                snapshot['mails'].append(mail)
                if case:
                    case['mail_ids'].append(mail['id'])
                    times = [m['sent_at'][:10] for m in snapshot['mails'] if m['id'] in case['mail_ids']]
                    case['period'] = [min(times), max(times)]
                else:
                    snapshot.setdefault('non_cases', []).append({**mail, 'type': 'alert'})
                with self._lock:
                    # NEW is acknowledged independently; preserve reads made during classification.
                    read_ids = {m['id'] for m in self._indexed['mails'] if m.get('_is_new') is False}
                    for m in snapshot['mails']:
                        if m['id'] in read_ids:
                            m['_is_new'] = False
                    self._indexed = snapshot
                    self.revision += 1
                    self._stage(event_id, 'saved', mail=mail, mail_url='/#mail-' + mail['id'])
            except Exception:
                self._stage(event_id, 'failed', error='수신 메일을 저장하지 못했어요. 다시 수신해 주세요.')

    def mark_read(self, mail_id):
        with self._lock:
            mail = next((m for m in self._indexed['mails'] if m['id'] == mail_id), None)
            if mail is None:
                return False
            if mail.get('_is_new'):
                mail['_is_new'] = False
                self.revision += 1
            return True
