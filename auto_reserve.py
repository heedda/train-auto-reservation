# coding=utf-8

import json
import time
from datetime import datetime

from letskorail import Korail
from letskorail.options import AdultPsg
from letskorail.exceptions import NoResultsError, SoldOutError

# --- 설정 파일 로드 ---
def load_config():
    """config.json 파일에서 사용자 정보를 읽어옵니다."""
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("오류: config.json 파일을 찾을 수 없습니다.")
        print("프로젝트 루트에 config.json 파일을 생성하고 코레일 아이디와 비밀번호를 입력하세요.")
        exit()
    except json.JSONDecodeError:
        print("오류: config.json 파일의 형식이 잘못되었습니다.")
        exit()

# --- 메인 로직 ---
def main():
    # 1. 설정 파일에서 모든 정보 로드
    config = load_config()
    KORAIL_ID = config.get("korail_id")
    KORAIL_PW = config.get("korail_pw")
    dep = config.get("departure_station")
    arr = config.get("arrival_station")
    date_str = config.get("date") or datetime.now().strftime("%Y%m%d") # config에 없으면 오늘 날짜
    max_arr_time_str = config.get("max_arrival_time")

    # 필수 설정값 확인
    if not all([KORAIL_ID, KORAIL_PW, dep, arr, max_arr_time_str]):
        print("오류: config.json 파일에 'korail_id', 'korail_pw', 'departure_station', 'arrival_station', 'max_arrival_time' 필드를 모두 설정해야 합니다.")
        return

    try:
        max_arr_time = int(max_arr_time_str)
    except ValueError:
        print("오류: config.json의 'max_arrival_time' 형식이 잘못되었습니다. HHMMSS 형식으로 입력하세요.")
        return

    print("--- KTX 자동 예매 시작 ---")
    print(f"출발역: {dep}, 도착역: {arr}, 날짜: {date_str}, 최대 도착 시간: {max_arr_time_str}")

    # 2. 코레일 로그인
    korail = Korail()
    try:
        profile = korail.login(KORAIL_ID, KORAIL_PW)
        print(f"\n로그인 성공: {profile.name}님 환영합니다.")
    except Exception as e:
        print(f"로그인 실패: {e}")
        return

    # 3. 목표 열차 확정 (Top 2 ONLY, 매진 여부 상관 없음)
    print("\n목표 열차를 확정합니다...")
    try:
        # 초기 검색 시에는 매진 포함하여 모든 열차를 가져옴
        all_trains_initial = korail.search_train(dep, arr, date_str, "000000", passengers=[AdultPsg(1)], include_soldout=True)
        priority_list_initial = [t for t in all_trains_initial if int(t.arv_time) < max_arr_time]

        if not priority_list_initial:
            print("오류: 조건에 맞는 열차가 없습니다. 프로그램을 종료합니다.")
            korail.logout()
            return

        priority_list_initial.sort(key=lambda t: int(t.dpt_time), reverse=True)
        
        # 목표 열차는 train_no로 고정 (매진 여부와 상관없이)
        p1_train_target_no = priority_list_initial[0].train_no if len(priority_list_initial) > 0 else None
        p2_train_target_no = priority_list_initial[1].train_no if len(priority_list_initial) > 1 else None

        print("\n--- 아래 최대 2개 열차의 좌석만 집중적으로 탐색합니다 ---")
        if p1_train_target_no:
            print(f"1순위: {priority_list_initial[0].info}")
        if p2_train_target_no:
            print(f"2순위: {priority_list_initial[1].info}")
        print("--------------------------------------------------------")

    except Exception as e:
        print(f"초기 열차 검색 중 오류 발생: {e}")
        korail.logout()
        return

    # 4. 예약 업그레이드 로직 (Strict Top 2)
    current_reservation = None # 현재 확보한 예약 (2순위일 수 있음)
    best_choice_booked = False # 1순위 예약 성공 여부
    
    while not best_choice_booked:
        try:
            # 매번 모든 열차 정보를 새로 가져옴 (매진 포함)
            current_all_trains = korail.search_train(dep, arr, date_str, "000000", passengers=[AdultPsg(1)], include_soldout=True)

            print(f"\r{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 좌석 탐색 중...", end="")

            # --- 1순위 열차 확인 (항상 최우선) ---
            if p1_train_target_no:
                found_p1_current_status = next((t for t in current_all_trains if t.train_no == p1_train_target_no), None)

                if found_p1_current_status and found_p1_current_status.has_seat():
                    print("\n\n✅ 1순위 좌석 발견! 최종 예약을 진행합니다.")
                    if current_reservation:
                        print(f"기존 2순위 예약을 취소합니다: [{current_reservation.info.splitlines()[0]}]")
                        korail.cancel(current_reservation)
                        current_reservation = None # 2순위 예약 해제
                    
                    final_reservation = korail.reserve(found_p1_current_status)
                    print(f"🎉 최종 예약 성공!\n{final_reservation.info}")
                    print("\n★★★ 중요 ★★★")
                    print("예약 후 20분 내에 코레일 앱이나 웹사이트에서 결제를 완료해야 합니다.")
                    best_choice_booked = True
                    continue # while 루프 종료

            # --- 2순위 열차 확인 (1순위가 아직 없고, 현재 예약도 없을 때만) ---
            # 1순위가 예약되지 않았고, 현재 아무 예약도 확보하지 못했을 때만 2순위 확인
            if not best_choice_booked and not current_reservation and p2_train_target_no:
                found_p2_current_status = next((t for t in current_all_trains if t.train_no == p2_train_target_no), None)

                if found_p2_current_status and found_p2_current_status.has_seat():
                    print("\n\n✅ 2순위 좌석 발견! 임시 예약합니다.")
                    current_reservation = korail.reserve(found_p2_current_status)
                    print(f"임시 예약 성공: {current_reservation.info.splitlines()[0]}")
                    print("이제 1순위 열차의 좌석만 계속 탐색합니다.")
                    # 2순위 예약 성공 후에는 더 이상 2순위 좌석을 찾지 않음 (current_reservation이 True가 됨)

            time.sleep(1)

        except Exception as e:
            print(f"\n탐색 루프 중 오류 발생: {e}. 5초 후 다시 시도합니다.")
            time.sleep(5)

    # 5. 최종 로그아웃
    korail.logout()
    print("\n로그아웃 되었습니다.")

if __name__ == "__main__":
    main()