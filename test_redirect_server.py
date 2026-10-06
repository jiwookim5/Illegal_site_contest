#!/usr/bin/env python3
"""
리다이렉트 테스트 서버
포트 5000에서 실행되며, 여러 시나리오를 제공합니다.
"""

from flask import Flask, redirect, render_template_string

app = Flask(__name__)

@app.route('/test1')
def test1():
    """단순 리다이렉트 (301)"""
    return redirect('/final', code=301)

@app.route('/test2')
def test2():
    """302 리다이렉트"""
    return redirect('/intermediate', code=302)

@app.route('/intermediate')
def intermediate():
    """중간 페이지 → 최종 페이지로 리다이렉트"""
    return redirect('/final', code=302)

@app.route('/test3')
def test3():
    """3단계 리다이렉트 체인"""
    return redirect('/step2', code=301)

@app.route('/step2')
def step2():
    return redirect('/step3', code=302)

@app.route('/step3')
def step3():
    return redirect('/final', code=301)

@app.route('/test-gambling')
def test_gambling():
    """도박 사이트로 리다이렉트 (의도적 테스트)"""
    return redirect('/fake-casino', code=302)

@app.route('/fake-casino')
def fake_casino():
    """불법광고 페이지"""
    html = '''
    <html>
    <head><title>카지노 사이트</title></head>
    <body>
        <h1>최고의 카지노 사이트에 오신 것을 환영합니다!</h1>
        <p>지금 바로 가입하고 보너스 100만원을 받으세요!</p>
        <p>토토, 바카라, 슬롯머신 - 모두 가능합니다!</p>
        <a href="#">클릭해서 입금하기</a>
    </body>
    </html>
    '''
    return html

@app.route('/final')
def final():
    """최종 페이지 (정상)"""
    html = '''
    <html>
    <head><title>최종 페이지</title></head>
    <body>
        <h1>최종 페이지</h1>
        <p>리다이렉트 테스트 완료!</p>
        <p>이 페이지는 합법적인 콘텐츠입니다.</p>
    </body>
    </html>
    '''
    return html

@app.route('/test-list')
def test_list():
    """테스트 목록"""
    html = '''
    <html>
    <head><title>리다이렉트 테스트</title></head>
    <body style="font-family: Arial; padding: 20px;">
        <h1>🧪 리다이렉트 테스트 서버</h1>

        <h2>정상 리다이렉트 (정상 콘텐츠로)</h2>
        <ul>
            <li><a href="/test1">테스트 1: 단순 301 리다이렉트</a></li>
            <li><a href="/test2">테스트 2: 2단계 리다이렉트</a></li>
            <li><a href="/test3">테스트 3: 3단계 리다이렉트 체인</a></li>
        </ul>

        <h2>🚨 불법광고 리다이렉트 (탐지 테스트)</h2>
        <ul>
            <li><a href="/test-gambling">테스트: 카지노로 리다이렉트 (탐지되어야 함)</a></li>
        </ul>

        <h2>📝 테스트 커맨드</h2>
        <pre>
# curl로 테스트 (리다이렉트 따라가기)
curl -L http://localhost:5000/test1 -v

# Python requests
python3 -c "import requests; r = requests.get('http://localhost:5000/test1', allow_redirects=True); print(r.url)"
        </pre>
    </body>
    </html>
    '''
    return html

@app.route('/')
def index():
    return redirect('/test-list')

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🧪 리다이렉트 테스트 서버 시작")
    print("="*60)
    print("\n📱 접속 주소: http://localhost:5000")
    print("📋 테스트 목록: http://localhost:5000/test-list")
    print("\n테스트 시나리오:")
    print("  /test1       → 단순 301 리다이렉트")
    print("  /test2       → 2단계 리다이렉트")
    print("  /test3       → 3단계 리다이렉트 체인")
    print("  /test-gambling → 카지노로 리다이렉트 (탐지 테스트)")
    print("\n" + "="*60 + "\n")

    app.run(debug=False, host='0.0.0.0', port=8888)
