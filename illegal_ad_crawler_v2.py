#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
불법광고 탐지 도구 — URL 기반 크롤러 v2
- URLs.csv 파일에서 URL 읽기
- 각 URL 방문해서 텍스트 추출
- 결과 CSV에 저장
"""

import requests
from bs4 import BeautifulSoup
import csv
import time
import os
from datetime import datetime


class URLBasedCrawler:
    def __init__(self, url_file="urls.csv", output_file="illegal_ads_data.csv"):
        self.url_file = url_file
        self.output_file = output_file
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # 출력 CSV 초기화
        self._init_output_csv()

    def _init_output_csv(self):
        """출력 CSV 파일 생성"""
        if not os.path.exists(self.output_file):
            with open(self.output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['카테고리', '키워드', 'URL', '텍스트', '수집_날짜'])
                writer.writeheader()

    def load_urls(self):
        """urls.csv에서 URL 로드"""
        if not os.path.exists(self.url_file):
            print(f"❌ {self.url_file} 파일을 찾을 수 없습니다.")
            print(f"\n먼저 아래 형식으로 {self.url_file}을 작성하세요:")
            print("카테고리,키워드,URL")
            print("도박,토토,https://kmedi.ddm.go.kr/...")
            return []

        urls = []
        try:
            with open(self.url_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('URL'):
                        urls.append(row)
        except Exception as e:
            print(f"❌ 파일 읽기 오류: {e}")
            return []

        return urls

    def extract_page_text(self, url):
        """페이지에서 텍스트 추출"""
        try:
            response = self.session.get(url, timeout=10)
            response.encoding = 'utf-8'
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"  ⚠️ 연결 실패")
            return None

        try:
            soup = BeautifulSoup(response.content, 'html.parser')

            # 텍스트 추출 (스크립트, 스타일 제외)
            for script in soup(["script", "style"]):
                script.decompose()

            text = soup.get_text(separator=' ', strip=True)
            # 공백 정규화
            text = ' '.join(text.split())
            return text[:500] if text else None  # 처음 500글자만
        except Exception as e:
            print(f"  ⚠️ 파싱 실패")
            return None

    def crawl_urls(self):
        """모든 URL 크롤링"""
        urls = self.load_urls()

        if not urls:
            print("❌ 크롤링할 URL이 없습니다.")
            return 0

        print("="*60)
        print(f"URL 기반 크롤러 시작 ({len(urls)}개 URL)")
        print("="*60)

        added_count = 0

        for i, url_info in enumerate(urls, 1):
            category = url_info.get('카테고리', '미분류')
            keyword = url_info.get('키워드', '알 수 없음')
            url = url_info.get('URL', '').strip()

            if not url:
                print(f"[{i}/{len(urls)}] ⚠️ URL 없음")
                continue

            print(f"[{i}/{len(urls)}] {url[:60]}...", end=" ")

            text = self.extract_page_text(url)
            if text:
                self.add_to_csv(category, keyword, url, text)
                print("✓ 저장됨")
                added_count += 1
            else:
                print("⚠️ 텍스트 없음")

            # 요청 간 딜레이
            time.sleep(1)

        print("\n" + "="*60)
        print(f"✓ 크롤링 완료: {added_count}/{len(urls)}건 수집됨")
        print(f"✓ 저장 위치: {self.output_file}")
        print("="*60)

        return added_count

    def add_to_csv(self, category, keyword, url, text):
        """CSV에 데이터 추가"""
        with open(self.output_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['카테고리', '키워드', 'URL', '텍스트', '수집_날짜'])
            writer.writerow({
                '카테고리': category,
                '키워드': keyword,
                'URL': url,
                '텍스트': text,
                '수집_날짜': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })


def main():
    print("불법광고 탐지 도구 — URL 기반 크롤러\n")

    crawler = URLBasedCrawler()

    print("선택:")
    print("1. urls.csv에서 URL 읽고 크롤링")
    print("2. urls.csv 템플릿 생성")
    print("3. 종료")

    choice = input("\n선택 (1-3): ").strip()

    if choice == '1':
        crawler.crawl_urls()
    elif choice == '2':
        print("\nurls.csv 템플릿 생성 중...")
        with open('urls.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['카테고리', '키워드', 'URL'])
            writer.writeheader()
            # 예시 데이터
            writer.writerow({
                '카테고리': '도박',
                '키워드': '토토',
                'URL': 'https://kmedi.ddm.go.kr/slot=토토 입플 사이트'
            })
            writer.writerow({
                '카테고리': '도박',
                '키워드': '토토',
                'URL': 'https://gongdan.go.kr/...'
            })
        print("✓ urls.csv 생성됨")
        print("  파일을 열어서 URL을 추가하세요!")
    elif choice == '3':
        print("종료합니다.")
    else:
        print("❌ 잘못된 선택입니다.")


if __name__ == "__main__":
    main()
