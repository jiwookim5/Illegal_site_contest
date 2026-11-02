"""Local UI layout and failed-stop response checks; scan state is synthetic."""
from datetime import datetime
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import threading
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'detector'))
from playwright.sync_api import sync_playwright
from ui.server import Handler,Session

def main():
    out=ROOT/'_regress'/('scan-ui-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    out.mkdir(parents=True)
    session=Session(str(out))
    class UI(Handler):
        def log_message(self,*a):pass
    UI.session=session
    server=ThreadingHTTPServer(('127.0.0.1',0),UI)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            page=browser.new_page(viewport={'width':1200,'height':800})
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{server.server_port}')
            # 주소를 비우고 시작하면 형식 오류가 아니라 입력 안내를 보인다
            empty=page.request.post(f'http://127.0.0.1:{server.server_port}/api/scan',data={'url':'  '})
            assert empty.status==400 and empty.json()['error']=='점검할 누리집 주소를 입력하십시오.',empty.text()
            # 추가 탐색은 시작 화면에 없고, 결과 화면에서 고를 때만 여는 별도 단계다
            assert page.locator('#start #search-assist').count()==0
            assert page.locator('#searchstage #search-assist').count()==1
            assert page.locator('.gnb #apihealth').is_visible()
            layout=[]
            for width,height in ((940,620),(1200,820),(1600,1000)):
                page.set_viewport_size({'width':width,'height':height})
                for stage in ('start','running','result','search'):
                    page.evaluate('(stage) => setStage(stage)',stage)
                    bounds=page.evaluate('''() => {
                        const panel=[...document.querySelectorAll('.stage')].find(e=>!e.hidden);
                        const p=panel.getBoundingClientRect(),f=document.querySelector('footer').getBoundingClientRect();
                        return {panelBottom:p.bottom,footerTop:f.top,footerBottom:f.bottom,footerHeight:f.height,
                                viewport:innerHeight,width:innerWidth,scrollWidth:document.documentElement.scrollWidth};
                    }''')
                    assert abs(bounds['footerHeight']-30)<1,bounds
                    assert abs(bounds['footerBottom']-height)<1,bounds
                    assert bounds['panelBottom']<=bounds['footerTop'],bounds
                    assert bounds['scrollWidth']<=width,bounds
                    if stage=='running':
                        page.locator('#stop').scroll_into_view_if_needed()
                        stop=page.locator('#stop').bounding_box()
                        assert stop['y']+stop['height']<=bounds['footerTop'],stop
                    layout.append(dict(stage=stage,**bounds))
            (out/'layout.json').write_text(json.dumps(layout,indent=2),encoding='utf-8')
            page.set_viewport_size({'width':1200,'height':800})
            page.evaluate("setStage('search')")
            page.locator('#search-site').fill('example.test')
            page.screenshot(path=str(out/'input.png'),full_page=True)
            session.running=True
            session.scan_status={'visited':108,'pending':137,'failed_count':1}
            page.evaluate("startRunning('http://127.0.0.1/example')")
            page.wait_for_function("document.getElementById('rc-pending').textContent === '137'")
            assert page.locator('#search-assist').is_hidden()
            assert page.locator('#stop').is_visible()
            box=page.locator('#stop').bounding_box()
            assert box['y']+box['height']<=800,box
            page.route('**/api/stop',lambda route:route.fulfill(status=500,content_type='application/json',body='{"error":"test stop failure"}'))
            page.locator('#stop').click()
            page.wait_for_function("document.getElementById('stop').textContent === '중지 다시 요청'")
            assert page.locator('#stop').is_enabled()
            page.unroute('**/api/stop')
            page.locator('#stop').click()
            # 누른 직후에는 요청이 아직 서버에 닿지 않았을 수 있다
            for _ in range(50):
                if session.stop_requested: break
                page.wait_for_timeout(100)
            assert session.stop_requested
            page.screenshot(path=str(out/'running.png'),full_page=True)
            now=datetime.now().astimezone()
            session.result=dict(started=now,finished=now,elapsed=4,engine_elapsed=2,process_elapsed=3,
                                pages=['http://127.0.0.1/example'],findings=[],
                                ocr_images={'read':0,'unavailable':'이 PC 에 한국어 글자 인식 언어가 없습니다'},coverage={'left_count':3,'left':['http://127.0.0.1/a','http://127.0.0.1/b','http://127.0.0.1/c'],'max_pages':1,'failed_count':0})
            session.running=False
            # Let the real completion poll finish and clear its timer before testing result controls.
            page.wait_for_function("document.getElementById('app').dataset.stage === 'result'")
            assert page.locator('#search-site').input_value()=='example.test'
            assert '부분 결과' in page.locator('#st-left').inner_text()
            text=page.locator('body').text_content()
            # 개발자용 시간 기록은 화면에 내지 않고, 그림 속 글자 검사를 못 했으면 알린다
            assert '전체 기록' not in text and '엔진 2.0초' not in text,text
            assert '그림 속 글자 검사를 하지 못했습니다: 이 PC 에 한국어 글자 인식 언어가 없습니다' in text,text
            path='C:\\점검 기록\\'+'긴 폴더 이름\\'*30+'runs\\sample'
            page.evaluate('(path) => setArchivePath(path)',path)
            right=page.locator('#st-right').bounding_box()
            left=page.locator('#st-left').bounding_box()
            assert left['x']+left['width']<=right['x'],(left,right)
            assert page.locator('#st-right').get_attribute('title')==path
            page.locator('#st-right').click()
            assert page.locator('#recordpathdlg').is_visible()
            assert page.locator('#recordpathtext').inner_text()==path
            page.locator('#recordpathdlg button').click()
            page.screenshot(path=str(out/'result.png'),full_page=True)
            page.on('dialog',lambda dialog:dialog.accept())
            page.route('**/api/quit',lambda route:route.fulfill(status=500,content_type='application/json',body='{"error":"test quit failure"}'))
            page.locator('#quit').click()
            # 브라우저 기본 창(제목에 주소·포트) 대신 화면 안 확인 창을 쓴다. 취소하면 아무 일도 없다
            assert page.locator('#askdlg').is_visible()
            assert page.locator('#askh').inner_text()=='프로그램 종료'
            assert page.locator('#askcancel').evaluate('(e) => e === document.activeElement')
            page.keyboard.press('Escape')
            assert not page.locator('#askdlg').is_visible()
            assert page.locator('#quit').inner_text()=='프로그램 종료'
            page.locator('#quit').click()
            page.screenshot(path=str(out/'quit-confirm.png'))
            page.locator('#askok').click()
            page.wait_for_function("document.getElementById('st-left').textContent.includes('종료 요청을 처리하지 못했습니다')")
            assert page.locator('#quit').is_enabled()
            assert not page.evaluate("document.getElementById('app').inert")
            assert not page.locator('.closed').count()
            assert not errors,errors
            browser.close()
        print('PASS: 12 viewport/stage layouts, scrollable content, queue copy, full record path, stop/quit failure retries, preserved search input, zero JS errors')
        print(out)
    finally:server.shutdown();server.server_close()
if __name__=='__main__':main()
