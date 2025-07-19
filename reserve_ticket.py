# coding=utf-8

import os
from datetime import datetime
from getpass import getpass

from letskorail import Korail
from letskorail.options import AdultPsg
from letskorail.exceptions import NoResultsError, SoldOutError

# --- 사용자 정보 입력 ---
# 코레일 아이디(멤버십 번호, 이메일, 전화번호)와 비밀번호를 입력하세요.
# 스크립트 실행 시 터미널에서 직접 입력받아 안전합니다.
KORAIL_ID = input("코레일 아이디: ")
KORAIL_PW = getpass("코레일 비밀번호: ")
# ----------------------

# 1. 코레일 객체 생성
korail = Korail()

# 2. 로그인
try:
    profile = korail.login(KORAIL_ID, KORAIL_PW)
    print(f"로그인 성공: {profile.name}님 환영합니다.")
except Exception as e:
    print(f"로그인 실패: {e}")
    exit()

# 3. 열차 검색
# 검색 조건
DEP = "수원"  # 출발지
ARR = "대전"  # 도착지
DATE = datetime.now().strftime("%Y%m%d")  # 오늘 날짜 (YYYYMMDD)
TIME = "000000"  # 00시 00분 00초 (오늘 첫차부터 검색)
PASSENGERS = [AdultPsg(1)]  # 성인 1명

try:
    print(f"\n{DATE} 날짜, {DEP} -> {ARR}행 열차를 검색합니다...")
    trains = korail.search_train(DEP, ARR, DATE, TIME, passengers=PASSENGERS)
except NoResultsError as e:
    print(f"열차 검색 실패: {e}")
    exit()

# 4. 10시 이전 도착 열차 중 가장 늦게 출발하는 열차 선택
target_train = None
latest_dpt_time = -1  # 가장 늦은 출발 시간을 추적

print("\n10시 이전 도착 가능한 열차 목록:")
for train in trains:
    # arv_time은 "hhmmss" 형식의 문자열이므로 정수로 변환하여 비교
    if int(train.arv_time) < 100000:
        print(f"- {train.info}")
        # 가장 늦게 출발하는 기차를 선택
        if int(train.dpt_time) > latest_dpt_time:
            latest_dpt_time = int(train.dpt_time)
            target_train = train

if not target_train:
    print("\n오전 10시 이전에 도착하는 예약 가능한 열차가 없습니다.")
    exit()


# 5. 열차 예약
try:
    print(f"\n가장 늦게 출발하는 열차로 예약을 진행합니다: {target_train.info}")
    reservation = korail.reserve(target_train)
    print("\n✅ 예약 성공!")
    print(reservation.info)
    print("\n★★★ 중요 ★★★")
    print("예약 후 20분 내에 코레일 앱이나 웹사이트에서 결제를 완료해야 합니다.")
    print("결제하지 않으면 예약이 자동 취소됩니다.")

except SoldOutError:
    print("예약 실패: 해당 열차의 좌석이 매진되었습니다.")
except Exception as e:
    print(f"예약 중 오류가 발생했습니다: {e}")

finally:
    # 6. 로그아웃
    korail.logout()
    print("\n로그아웃 되었습니다.")
