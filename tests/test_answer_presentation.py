"""Answer presentation and recent-mail routing regressions."""
from app.answer_format import format_answer
from app.search import answer_question, _is_recent_summary


def test_markdown_hierarchy_and_tables():
    result = format_answer({'answer': '**요약**입니다.\n\n## 핵심 내용\n\n- 첫 항목\n- 둘째 항목\n\n| 항목 | 값 |\n|---|---|\n| 금액 | 48,500,000원 |'})
    html = result['answer_html']
    assert '<strong>요약</strong>' in html
    assert '<h2>핵심 내용</h2>' in html
    assert '<ul>' in html and '<table>' in html


def test_untrusted_html_and_urls_do_not_execute():
    html = format_answer({'answer':'<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\n[click](javascript:alert(1))\n\n![remote](https://example.com/tracker.png)'})['answer_html']
    assert '<script' not in html and '<img' not in html
    assert 'href="javascript:' not in html
    assert '&lt;script&gt;' in html


def _mails():
    return [{'id': f'm{i:02}', 'subject':f'메일 {i}', 'sender_name':'김담당',
             'sent_at':f'2026-09-{i:02}T10:00:00', 'body':f'공지 내용 {i}'} for i in range(1,16)]


def test_recent_summary_uses_latest_mails_not_attachments():
    captured=[]
    result=answer_question('최근 메일 요약해봐', {'mails':_mails()}, lambda p: captured.append(p) or '최근 공지 요약입니다.')
    assert result['kind']=='mail_summary'
    assert result['mail_ids']==[f'm{i:02}' for i in range(15,3,-1)]
    assert result['attachment'] is None and result['evidence']==[]
    assert '2026-09-04 – 2026-09-15' in result['scope']
    assert '메일 15' in captured[0] and '첨부 정답을 하나 고르는 작업이 아니다' in captured[0]
    assert not result['cached']


def test_summary_offline_is_honest_and_grounded():
    def offline(_): raise RuntimeError('offline')
    result=answer_question('최근 메일 요약해봐',{'mails':_mails()},offline)
    assert result['cached'] and '제목을 모았습니다' in result['answer']
    assert len(result['sources'])==12
    assert '48,500,000' not in result['answer']


def test_empty_mailbox_does_not_load_demo_data():
    result=answer_question('최근 메일 요약해봐',{'mails':[]},lambda _: 'should not run')
    assert result['mail_ids']==[] and '없습니다' in result['answer']


def test_project_specific_question_is_not_global_summary():
    assert not _is_recent_summary('N_CX 최근 메일 요약해봐')
    assert not _is_recent_summary('최근 메일 3통 요약해줘')
    assert _is_recent_summary('최근 받은 메일을 요약해 주세요')


def test_page_and_ask_response_contract():
    from fastapi.testclient import TestClient
    from app.main import app
    client=TestClient(app)
    page=client.get('/')
    assert page.status_code==200 and 'answer-dialog' in page.text
    response=client.post('/ask',json={'question':'최근 메일 요약해봐'})
    assert response.status_code==200
    assert '<' in response.json()['answer_html']
    assert response.json()['kind']=='mail_summary'


def test_missing_id_never_uses_example_document():
    import pytest
    from agent.harness import ToolHarness
    from agent.skills import default_skills
    from agent.classifier_adapter import ClassifierAdapter
    harness=ToolHarness(default_skills(ClassifierAdapter()))
    with pytest.raises(ValueError): harness.execute('get_attachment_text',{})
    with pytest.raises(ValueError): harness.execute('get_case_emails',{'case_id':123})
    with pytest.raises(ValueError): harness.execute('get_tree',[])


def test_repeated_tool_executes_once_and_preserves_result():
    from agent.orchestrator import Orchestrator
    from agent.harness import ToolHarness
    from agent.skills import Skill
    calls=[]
    harness=ToolHarness([Skill('get_tree','업무 목록',lambda _:calls.append(1) or {'cases':[{'title':'실제 업무'}]})])
    orch=Orchestrator(harness,lambda _: '{"tool":"get_tree","arguments":{}}',max_steps=4)
    assert '실제 업무' in orch.run('업무 목록')
    assert len(calls)==1


def test_web_agent_summary_preserves_metadata_and_shared_tone():
    from agent.manager import ManagerAgent
    prompts=[]
    manager=ManagerAgent(indexed={'mails':_mails()},llm_call=lambda p:prompts.append(p) or '최근 안내가 모여 있어요.\n\n## 핵심 내용\n\n- 공지를 확인해 보세요.')
    result=manager.run_result('최근 메일 요약해봐')
    assert result['kind']=='mail_summary' and len(result['sources'])==12
    assert '해요체' in prompts[0]
    assert manager.context.steps_history()[0]['tool']=='summarize_recent_mail'
    assert result['cached'] is False


def test_unrelated_question_does_not_invent_a_document():
    import json
    from pathlib import Path
    indexed=json.loads(Path('data/indexed.json').read_text(encoding='utf-8'))
    result=answer_question('화성여행계획',indexed,lambda _: 'random answer')
    assert result['attachment'] is None and result['evidence']==[]


def test_tool_prompt_includes_schema_and_actual_document_not_truncated():
    from agent.manager import ManagerAgent
    manager=ManagerAgent()
    prompt=manager.orchestrator._tool_prompt('첨부', '앞 내용'*200+'최종값 48500000')
    assert 'required' in prompt and '최종값 48500000' in prompt
    assert '해요체' in prompt
