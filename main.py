import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone


# --------------------------------------------------
# 1. 기본 페이지 설정
# --------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)


# --------------------------------------------------
# 2. 한국 시간 기준으로 '어제' 날짜 계산
# --------------------------------------------------
# Streamlit Cloud 서버가 한국 시간이 아닐 수 있기 때문에
# 서버의 현재 시간을 그대로 사용하지 않고
# 한국 표준시(KST, UTC+9)를 직접 계산합니다.

KST = timezone(timedelta(hours=9))
now_kst = datetime.now(KST)

# 오늘에서 하루를 빼면 '어제'입니다.
yesterday = now_kst - timedelta(days=1)

# KOBIS API가 요구하는 날짜 형식: YYYYMMDD
target_date = yesterday.strftime("%Y%m%d")

# 화면에 보여주기 좋은 날짜 형식
display_date = yesterday.strftime("%Y년 %m월 %d일")


# --------------------------------------------------
# 3. 페이지 제목
# --------------------------------------------------

st.title("🎬 어제의 박스오피스")
st.write(f"**조회 날짜: {display_date}**")
st.caption("KOBIS 일별 박스오피스 기준 · 한국 시간")


# --------------------------------------------------
# 4. KOBIS API 호출 함수
# --------------------------------------------------
# @st.cache_data를 사용하면 같은 날짜의 데이터를
# 계속 API에 요청하지 않습니다.
#
# ttl=3600 → 1시간 동안 같은 결과를 기억합니다.
#
# 즉, 한 시간 안에 앱을 다시 실행해도
# 같은 날짜의 API를 다시 호출하지 않습니다.

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    # Streamlit Cloud의 Secrets에서 인증키를 가져옵니다.
    # 실제 인증키는 코드에 절대 적지 않습니다.
    try:
        api_key = st.secrets["KOBIS_KEY"]
    except Exception:
        return {
            "success": False,
            "message": (
                "KOBIS 인증키를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud의 앱 설정에서 "
                "`Secrets`에 `KOBIS_KEY`가 등록되어 있는지 확인해 주세요."
            ),
            "data": None
        }

    # KOBIS 공식 일별 박스오피스 API 주소
    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    # API에 보낼 요청값
    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류가 발생하면 예외를 발생시킵니다.
        response.raise_for_status()

        result = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": (
                "KOBIS API에 요청하는 중 문제가 발생했습니다.\n\n"
                "다음 사항을 확인해 주세요.\n"
                "1. 인터넷 연결 상태\n"
                "2. KOBIS API 서버 상태\n"
                "3. API 주소가 올바른지\n\n"
                f"오류 내용: {e}"
            ),
            "data": None
        }

    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS API에서 정상적인 JSON 데이터를 받지 못했습니다.\n\n"
                "KOBIS API 서버 상태를 확인해 주세요."
            ),
            "data": None
        }

    # --------------------------------------------------
    # 5. faultInfo 확인
    # --------------------------------------------------
    # KOBIS는 인증키가 잘못되어도 HTTP 상태코드가
    # 200으로 올 수 있습니다.
    # 따라서 faultInfo가 있는지 반드시 확인합니다.

    if "faultInfo" in result:
        fault = result["faultInfo"]

        fault_code = fault.get("errorCode", "알 수 없음")
        fault_message = fault.get("message", "알 수 없는 오류")

        return {
            "success": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                "특히 인증키가 올바른지 확인해 주세요.\n\n"
                f"오류 코드: {fault_code}\n"
                f"오류 내용: {fault_message}\n\n"
                "Streamlit Cloud → 앱 → Settings → Secrets에서 "
                "`KOBIS_KEY`가 정확하게 등록되어 있는지 확인하세요."
            ),
            "data": None
        }

    # --------------------------------------------------
    # 6. boxOfficeResult 확인
    # --------------------------------------------------

    boxoffice = result.get("boxOfficeResult")

    if not boxoffice:
        return {
            "success": False,
            "message": (
                "박스오피스 결과를 찾을 수 없습니다.\n\n"
                "KOBIS API의 응답 구조가 정상인지 확인해 주세요."
            ),
            "data": None
        }

    # 영화 목록 가져오기
    movie_list = boxoffice.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "success": False,
            "message": (
                f"{display_date}의 영화 목록이 비어 있습니다.\n\n"
                "다음 사항을 확인해 주세요.\n"
                "• 해당 날짜의 박스오피스 데이터가 실제로 존재하는지\n"
                "• 조회 날짜가 올바른지\n"
                "• KOBIS API 서버에 문제가 없는지"
            ),
            "data": None
        }

    return {
        "success": True,
        "message": "",
        "data": movie_list
    }


# --------------------------------------------------
# 7. API에서 데이터 가져오기
# --------------------------------------------------

result = get_boxoffice(target_date)


# --------------------------------------------------
# 8. 요청 실패 시 안내
# --------------------------------------------------

if not result["success"]:
    st.error("⚠️ 박스오피스 데이터를 가져오지 못했습니다.")

    # 줄바꿈이 들어 있는 안내문을 그대로 보여줍니다.
    st.warning(result["message"])

    st.stop()


# --------------------------------------------------
# 9. 영화 데이터를 표 형태로 변환
# --------------------------------------------------

movie_list = result["data"]

df = pd.DataFrame(movie_list)


# --------------------------------------------------
# 10. 숫자 데이터는 문자열이므로 숫자로 변환
# --------------------------------------------------
# KOBIS API의 숫자 데이터도 문자열로 전달되기 때문에
# 정렬과 그래프를 제대로 사용하려면 숫자로 변환해야 합니다.

number_columns = [
    "rank",
    "audiCnt",
    "audiAcc",
    "scrnCnt"
]

for column in number_columns:
    df[column] = pd.to_numeric(
        df[column],
        errors="coerce"
    ).fillna(0)


# --------------------------------------------------
# 11. 순위 기준으로 정렬
# --------------------------------------------------

df = df.sort_values("rank").reset_index(drop=True)


# --------------------------------------------------
# 12. 1위 영화 가져오기
# --------------------------------------------------

first_movie = df.iloc[0]


# --------------------------------------------------
# 13. 1위 영화 정보 크게 보여주기
# --------------------------------------------------

st.subheader("🏆 1위 영화")

st.markdown(
    f"## {first_movie['movieNm']}"
)

st.write(
    f"개봉일: {first_movie['openDt']}"
)


# 지표 카드 3개를 나란히 배치합니다.
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "오늘 관객수",
        f"{int(first_movie['audiCnt']):,}명"
    )

with col2:
    st.metric(
        "누적 관객수",
        f"{int(first_movie['audiAcc']):,}명"
    )

with col3:
    st.metric(
        "스크린수",
        f"{int(first_movie['scrnCnt']):,}개"
    )


# --------------------------------------------------
# 14. 전체 박스오피스 표
# --------------------------------------------------

st.subheader("📋 전체 박스오피스")

# 사용자에게 보여줄 열만 선택합니다.
display_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()

# 화면에서 보기 좋은 한글 열 이름으로 변경합니다.
display_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]

# 표에서 숫자를 천 단위 쉼표로 표시합니다.
st.dataframe(
    display_df.style.format({
        "순위": "{:,.0f}",
        "관객수": "{:,.0f}",
        "누적관객": "{:,.0f}",
        "스크린수": "{:,.0f}"
    }),
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# 15. 관객수 상위 5편 막대그래프
# --------------------------------------------------

st.subheader("📊 관객수 상위 5편")

# 관객수가 많은 순서로 정렬한 뒤 5편만 선택합니다.
top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)

# 그래프의 가로축은 영화명,
# 세로축은 관객수가 되도록 만듭니다.
chart_df = top5[
    ["movieNm", "audiCnt"]
].set_index("movieNm")

# Streamlit 기본 막대그래프 사용
st.bar_chart(
    chart_df,
    y="audiCnt",
    x_label="영화",
    y_label="관객수"
)


# --------------------------------------------------
# 16. 안내 문구
# --------------------------------------------------

st.caption(
    "※ 데이터 출처: 영화관입장권통합전산망(KOBIS) "
    "일별 박스오피스 API"
)
# 관객수가 많은 상위 5편을 먼저 선택합니다.
top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)

# 선택된 5편을 다시 관객수가 적은 순서로 정렬합니다.
top5 = top5.sort_values(
    "audiCnt",
    ascending=True
)

# 영화명과 관객수만 그래프에 사용합니다.
chart_df = top5[
    ["movieNm", "audiCnt"]
].set_index("movieNm")

# 관객수가 적은 영화부터 많은 영화 순서로 그래프 표시
st.bar_chart(
    chart_df,
    y="audiCnt",
    x_label="영화",
    y_label="관객수"
)
