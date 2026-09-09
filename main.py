import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone


# ---------------------------------------
# 1. 기본 설정
# ---------------------------------------

st.set_page_config(
    page_title="박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일일 박스오피스")


# ---------------------------------------
# 2. 한국 시간(KST) 기준 날짜 계산
# ---------------------------------------

KST = timezone(timedelta(hours=9))

now_kst = datetime.now(KST)

today = now_kst.date()

# 오늘은 아직 집계가 끝나지 않았으므로
# 조회 가능한 가장 늦은 날짜는 어제
yesterday = today - timedelta(days=1)


# ---------------------------------------
# 3. 날짜 선택
# ---------------------------------------

selected_date = st.date_input(
    "📅 조회할 날짜를 선택하세요",
    value=yesterday,
    min_value=datetime(2000, 1, 1).date(),
    max_value=yesterday
)

target_date = selected_date.strftime("%Y%m%d")

display_date = selected_date.strftime("%Y년 %m월 %d일")


# ---------------------------------------
# 4. KOBIS API에서 데이터 가져오기
# ---------------------------------------

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):

    try:
        # Streamlit Secrets에서 API 키 가져오기
        api_key = st.secrets["KOBIS_KEY"]

        url = (
            "https://www.kobis.or.kr/kobisopenapi/"
            "webservice/rest/boxoffice/"
            "searchDailyBoxOfficeList.json"
        )

        params = {
            "key": api_key,
            "targetDt": target_dt
        }

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        # API 오류
        if "faultInfo" in data:
            return None, "API_ERROR"

        # 박스오피스 결과가 없는 경우
        if "boxOfficeResult" not in data:
            return None, "NO_RESULT"

        movie_list = data["boxOfficeResult"].get(
            "dailyBoxOfficeList",
            []
        )

        # 영화 목록이 비어 있는 경우
        if not movie_list:
            return None, "EMPTY"

        return movie_list, None

    except KeyError:
        return None, "NO_KEY"

    except requests.exceptions.RequestException:
        return None, "CONNECTION_ERROR"

    except ValueError:
        return None, "DATA_ERROR"

    except Exception:
        return None, "UNKNOWN_ERROR"


# ---------------------------------------
# 5. 선택한 날짜 데이터 가져오기
# ---------------------------------------

movie_list, error_type = get_boxoffice(target_date)


# ---------------------------------------
# 6. 오류 처리
# ---------------------------------------

if error_type == "EMPTY":
    st.warning("📭 그날은 아직 집계 전입니다")
    st.stop()

elif error_type == "NO_KEY":
    st.error(
        "⚠️ KOBIS_KEY가 설정되어 있지 않습니다.\n\n"
        "Streamlit Cloud의 Secrets에 KOBIS_KEY를 등록해주세요."
    )
    st.stop()

elif error_type == "API_ERROR":
    st.error(
        "⚠️ KOBIS API에서 오류가 발생했습니다.\n\n"
        "API 키가 올바른지 확인해주세요."
    )
    st.stop()

elif error_type == "NO_RESULT":
    st.warning("📭 그날은 아직 집계 전입니다")
    st.stop()

elif error_type == "CONNECTION_ERROR":
    st.error(
        "⚠️ KOBIS API에 연결하지 못했습니다.\n\n"
        "잠시 후 다시 시도해주세요."
    )
    st.stop()

elif error_type == "DATA_ERROR":
    st.error(
        "⚠️ API에서 받은 데이터를 읽을 수 없습니다."
    )
    st.stop()

elif error_type == "UNKNOWN_ERROR":
    st.error(
        "⚠️ 알 수 없는 오류가 발생했습니다."
    )
    st.stop()


# ---------------------------------------
# 7. 날짜 표시
# ---------------------------------------

st.subheader(f"📅 {display_date} 박스오피스")


# ---------------------------------------
# 8. DataFrame으로 변환
# ---------------------------------------

df = pd.DataFrame(movie_list)


# ---------------------------------------
# 9. 숫자 데이터를 숫자로 변환
# ---------------------------------------

number_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt"
]

for column in number_columns:
    df[column] = pd.to_numeric(
        df[column],
        errors="coerce"
    ).fillna(0)


# 순위순으로 정렬
df = df.sort_values(
    by="rank",
    ascending=True
)


# ---------------------------------------
# 10. 1위 영화 보여주기
# ---------------------------------------

first_movie = df.iloc[0]

st.subheader("🏆 1위 영화")

st.markdown(
    f"## {int(first_movie['rank'])}위 · "
    f"{first_movie['movieNm']}"
)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "일일 관객 수",
        f"{int(first_movie['audiCnt']):,}명"
    )

with col2:
    st.metric(
        "누적 관객 수",
        f"{int(first_movie['audiAcc']):,}명"
    )

with col3:
    st.metric(
        "상영 스크린 수",
        f"{int(first_movie['scrnCnt']):,}개"
    )


# ---------------------------------------
# 11. 전체 박스오피스 표
# ---------------------------------------

st.subheader("🎞️ 전체 박스오피스")

display_df = df[
    [
        "rank",
        "rankInten",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


# ---------------------------------------
# 12. 누적 관객 100만 명 이상 트로피 표시
# ---------------------------------------

def add_trophy(row):

    movie_name = row["movieNm"]

    if row["audiAcc"] > 1_000_000:
        movie_name += " 🏆"

    return movie_name


display_df["movieNm"] = display_df.apply(
    add_trophy,
    axis=1
)


# ---------------------------------------
# 13. 순위 증감 표시
# ---------------------------------------

def rank_change(row):

    change = int(row["rankInten"])

    if change > 0:
        return f"🔺 +{change}"

    elif change < 0:
        return f"🔻 {change}"

    else:
        return "➖ 0"


display_df["rankInten"] = display_df.apply(
    rank_change,
    axis=1
)


# ---------------------------------------
# 14. 표의 열 이름 변경
# ---------------------------------------

display_df.columns = [
    "순위",
    "전일 대비",
    "영화명",
    "개봉일",
    "일일 관객 수",
    "누적 관객 수",
    "스크린 수"
]


# ---------------------------------------
# 15. 숫자에 쉼표 표시
# ---------------------------------------

display_df["일일 관객 수"] = display_df[
    "일일 관객 수"
].map(lambda x: f"{int(x):,}")

display_df["누적 관객 수"] = display_df[
    "누적 관객 수"
].map(lambda x: f"{int(x):,}")

display_df["스크린 수"] = display_df[
    "스크린 수"
].map(lambda x: f"{int(x):,}")


# ---------------------------------------
# 16. 전체 표 보여주기
# ---------------------------------------

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# ---------------------------------------
# 17. 관객 수 TOP 5 그래프
# ---------------------------------------

st.subheader("📊 관객 수 TOP 5")


# 먼저 관객 수가 가장 많은 영화 5편을 선택
top5 = df.sort_values(
    by="audiCnt",
    ascending=False
).head(5).copy()


# ---------------------------------------
# ⭐ 중요
# ---------------------------------------
# TOP 5를 관객 수 기준 "오름차순"으로 정렬
#
# 작은 관객 수
#       ↓
# 큰 관객 수
#
# 영화 이름이 아니라 audiCnt 숫자를 기준으로 정렬합니다.
top5 = top5.sort_values(
    by="audiCnt",
    ascending=True
).reset_index(drop=True)


# 그래프에 넣을 데이터
chart_df = pd.DataFrame({
    "영화명": top5["movieNm"].astype(str),
    "관객 수": top5["audiCnt"].astype(int)
})


# ---------------------------------------
# 관객 수 오름차순 그래프
# ---------------------------------------
#
# 왼쪽  → 관객 수 적음
# 오른쪽 → 관객 수 많음
#
# 따라서 가장 많은 관객 수를 가진 영화가
# 항상 그래프의 가장 뒤(오른쪽)에 위치합니다.

st.bar_chart(
    chart_df,
    x="영화명",
    y="관객 수",
    x_label="영화",
    y_label="관객 수"
)
