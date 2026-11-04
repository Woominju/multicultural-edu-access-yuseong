"""최소 단위 테스트: 프로그램 분류, 주소→시군구 키, 좌표 뒤바뀜 보정. 실행: python -I tests/test_units.py"""
import sys; sys.argv = ["x"]; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import nw_pipeline as P, pandas as pd
fail = 0
def check(c, msg):
    global fail
    print(("OK  " if c else "FAIL") + " " + msg); fail += (not c)
T = [("다문화자녀 기초학습 지원", "다문화가족 자녀(초등)", "A_"), ("결혼이민자와 함께하는 무한도전(초등검정고시대비반)", "결혼이민자", "B_"),
     ("[다가지2] 기초학습지원 다배움 고학년", "다문화,외국인,중도입국 초2-초4", "A_"), ("2026년 다문화가족 자녀 교육활동비", "다문화가족 자녀", "A2"),
     ("한국어 초급반(3기)", "결혼이민자 및 외국인 거주자", "B_"), ("부부 소통 프로그램", "부부", "C_"), ("아동 독서 교실", "초등학생", "B_")]
for n, t, e in T:
    r = P.classify_program(n, t, "")[0]; check(r.startswith(e), f"분류 {n} → {r}")
keys = {"31|수원시", "24|북구", "36|순천시", "29|세종시", "32|춘천시"}
check(P._addr_key("경기도 수원시 장안구 정자로 1", keys) == "31|수원시", "주소키 일반구→시")
check(P._addr_key("전남광주통합특별시 북구 설죽로 433", keys) == "24|북구", "주소키 전남광주통합(구→광주)")
check(P._addr_key("전남광주통합특별시 순천시 중앙로 1", keys) == "36|순천시", "주소키 전남광주통합(시→전남)")
check(P._addr_key("세종특별자치시 한누리대로 1", keys) == "29|세종시", "주소키 세종")
check(P._addr_key("강원도 춘천시 중앙로 1", keys) == "32|춘천시", "주소키 강원도(구명칭)")
g = P._to_points(pd.DataFrame({"위도": ["126.8", "37.3", "0"], "경도": ["37.3", "126.8", "0"]}), "위도", "경도")
check(list(g._coord_ok) == [True, True, False] and abs(g._lat.iloc[0] - 37.3) < 1e-9, "좌표 뒤바뀜 보정·이상값 제외")
print("FAILURES:", fail); sys.exit(1 if fail else 0)
