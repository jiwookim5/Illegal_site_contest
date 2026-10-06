#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
불법광고 탐지 도구 MVP
- 키워드 기반 탐지
- 테스트 데이터 수집 및 저장
- 탐지 결과 리포트 생성
"""

import csv
import json
import os
from datetime import datetime
from pathlib import Path


class IllegalAdDetector:
    def __init__(self, data_file="illegal_ads_data.csv", results_file="detection_results.json"):
        self.data_file = data_file
        self.results_file = results_file

        # 불법광고 키워드 (카테고리별)
        self.keywords = {
            "도박": ["토토", "바카라", "카지노", "홀덤", "슬롯", "슬롯머신", "첫충", "꽁머니", "배팅", "베팅"],
            "성인": ["야동", "성인", "포르노", "성인용품"],
            "마약": ["대마", "코카인", "필로폰", "마약", "히로뽕"],
        }

        # CSV 파일 초기화
        self._init_csv()

    def _init_csv(self):
        """CSV 파일이 없으면 생성, 있으면 유지"""
        if not os.path.exists(self.data_file):
            with open(self.data_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['카테고리', '키워드', 'URL', '텍스트', '수집_날짜'])
                writer.writeheader()
            print(f"✓ {self.data_file} 생성됨")

    def add_data(self, category, keyword, url, text):
        """테스트 데이터 추가"""
        with open(self.data_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['카테고리', '키워드', 'URL', '텍스트', '수집_날짜'])
            writer.writerow({
                '카테고리': category,
                '키워드': keyword,
                'URL': url,
                '텍스트': text,
                '수집_날짜': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        print(f"✓ 데이터 추가됨: [{category}] {keyword}")

    def detect(self, text):
        """텍스트에서 불법광고 탐지"""
        for category, words in self.keywords.items():
            for word in words:
                if word.lower() in text.lower():
                    return {
                        'detected': True,
                        'category': category,
                        'keyword': word,
                        'message': f"[불법광고 탐지] {category} - '{word}' 감지됨"
                    }
        return {
            'detected': False,
            'category': None,
            'keyword': None,
            'message': "[정상] 불법광고 없음"
        }

    def detect_batch(self, file_path):
        """CSV 파일의 모든 텍스트 탐지"""
        results = []

        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                text = row.get('텍스트', '')
                url = row.get('URL', '')
                detection = self.detect(text)
                detection['url'] = url
                detection['original_text'] = text
                results.append(detection)

        return results

    def save_results(self, results):
        """탐지 결과를 JSON으로 저장"""
        output = {
            'detection_time': datetime.now().isoformat(),
            'total_items': len(results),
            'detected_count': sum(1 for r in results if r['detected']),
            'results': results
        }

        with open(self.results_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\n✓ 결과 저장됨: {self.results_file}")
        return output

    def print_stats(self, results):
        """탐지 통계 출력"""
        detected = [r for r in results if r['detected']]
        category_count = {}

        for r in detected:
            cat = r.get('category')
            category_count[cat] = category_count.get(cat, 0) + 1

        print("\n" + "="*50)
        print("탐지 결과 통계")
        print("="*50)
        print(f"총 항목: {len(results)}")
        print(f"불법광고 탐지: {len(detected)}건")

        if category_count:
            print("\n카테고리별 탐지:")
            for cat, count in category_count.items():
                print(f"  - {cat}: {count}건")
        print("="*50 + "\n")

    def load_data(self):
        """저장된 데이터 조회"""
        if not os.path.exists(self.data_file):
            print("수집된 데이터가 없습니다.")
            return []

        with open(self.data_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)

    def delete_data(self, row_number):
        """특정 행 삭제"""
        data = self.load_data()

        if row_number < 1 or row_number > len(data):
            print(f"❌ 잘못된 번호입니다. (1-{len(data)} 범위)")
            return False

        # 삭제할 행을 제외하고 다시 저장
        remaining_data = data[:row_number-1] + data[row_number:]

        with open(self.data_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['카테고리', '키워드', 'URL', '텍스트', '수집_날짜'])
            writer.writeheader()
            writer.writerows(remaining_data)

        print(f"✓ [{row_number}번] 데이터 삭제됨")
        return True

    def clear_all_data(self):
        """모든 데이터 삭제 (초기화)"""
        confirm = input("\n⚠️ 정말 모든 데이터를 삭제하시겠습니까? (yes/no): ").strip().lower()

        if confirm == 'yes':
            with open(self.data_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['카테고리', '키워드', 'URL', '텍스트', '수집_날짜'])
                writer.writeheader()

            print("✓ 모든 데이터 삭제됨 (CSV 초기화)")
            return True
        else:
            print("❌ 취소됨")
            return False


def main():
    detector = IllegalAdDetector()

    print("불법광고 탐지 도구 MVP")
    print("-" * 50)

    while True:
        print("\n메뉴:")
        print("1. 데이터 추가 (수동 입력)")
        print("2. 데이터 조회")
        print("3. 전체 탐지 실행")
        print("4. 텍스트 탐지 (단일)")
        print("5. 데이터 삭제 (특정)")
        print("6. 데이터 초기화 (전체)")
        print("7. 종료")

        choice = input("\n선택 (1-7): ").strip()

        if choice == '1':
            print("\n--- 데이터 추가 ---")
            category = input("카테고리 (도박/성인/마약): ").strip()
            keyword = input("키워드: ").strip()
            url = input("URL: ").strip()
            text = input("텍스트: ").strip()

            if category and keyword and url and text:
                detector.add_data(category, keyword, url, text)
            else:
                print("❌ 모든 필드를 입력해주세요.")

        elif choice == '2':
            data = detector.load_data()
            if data:
                print(f"\n수집된 데이터 ({len(data)}건):")
                print("-" * 100)
                for i, row in enumerate(data, 1):
                    print(f"\n[{i}] {row.get('카테고리')} - {row.get('키워드')}")
                    print(f"    URL: {row.get('URL')}")
                    print(f"    텍스트: {row.get('텍스트')[:50]}...")
            else:
                print("데이터가 없습니다.")

        elif choice == '3':
            print("\n전체 탐지 실행 중...")
            results = detector.detect_batch(detector.data_file)
            detector.save_results(results)
            detector.print_stats(results)

        elif choice == '4':
            text = input("\n텍스트 입력: ").strip()
            result = detector.detect(text)
            print(f"\n결과: {result['message']}")

        elif choice == '5':
            print("\n--- 데이터 삭제 ---")
            data = detector.load_data()
            if data:
                print(f"\n수집된 데이터 ({len(data)}건):")
                print("-" * 100)
                for i, row in enumerate(data, 1):
                    print(f"[{i}] {row.get('카테고리')} - {row.get('키워드')} | {row.get('URL')[:50]}...")

                row_num = input("\n삭제할 번호 입력 (또는 엔터로 취소): ").strip()
                if row_num.isdigit():
                    detector.delete_data(int(row_num))
            else:
                print("삭제할 데이터가 없습니다.")

        elif choice == '6':
            detector.clear_all_data()

        elif choice == '7':
            print("종료합니다.")
            break

        else:
            print("❌ 잘못된 선택입니다.")


if __name__ == "__main__":
    main()
