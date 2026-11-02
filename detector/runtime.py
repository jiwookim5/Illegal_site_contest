"""실행 환경(소스 실행 / exe)에 따른 경로를 한곳에서 계산한다.

개발 중에는 프로젝트 폴더를, exe 로 묶이면 번들 폴더를 본다.
"""
import os
import sys


def bundle_dir():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def asset_path(name):
    """아이콘 등 동봉 자원의 경로. 없으면 None."""
    path = os.path.join(bundle_dir(), "assets", name)
    return path if os.path.exists(path) else None
