import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime

# ==============================================================================
# 0. 상수 및 설정 정의
# (두 번째 코드의 간결한 이름 사용)
# ==============================================================================

API_KEY = "f2907b0b1e074198de1ba6fb1928665f"

BASE_URL = "http://api.openweathermap.org/data/2.5/forecast"
GEO_URL = "http://api.openweathermap.org/geo/1.0/direct"
AIR_URL = "http://api.openweathermap.org/data/2.5/air_pollution"

# 날씨 설명 매핑 (W_DESC 사용)
W_DESC = {
    "clear sky": "맑음", "few clouds": "구름 조금", "scattered clouds": "구름 많음",
    "broken clouds": "구름 낌", "overcast clouds": "흐림", "light rain": "약한 비",
    "moderate rain": "보통 비", "heavy intensity rain": "폭우", "very heavy rain": "강한 폭우",
    "extreme rain": "극심한 비", "freezing rain": "진눈깨비", "light snow": "약한 눈",
    "snow": "눈", "heavy snow": "함박눈", "sleet": "진눈깨비", "shower rain": "소나기",
    "thunderstorm": "천둥 번개", "mist": "안개", "smoke": "연기", "haze": "안개",
    "sand": "모래", "dust": "황사/먼지", "fog": "짙은 안개", "squalls": "돌풍",
    "tornado": "태풍",
}

# AQI 상태 매핑 (AQI_TEXT 사용)
AQI_TEXT = {
    1: ("좋음", "🟢"), 2: ("보통", "🟡"), 3: ("나쁨", "🟠"),
    4: ("상당히 나쁨", "🔴"), 5: ("매우 나쁨", "⚫"),
}

# 요일 매핑 (UI 상세 구현을 위해 필요)
KR_WEEKDAYS = {0: '월', 1: '화', 2: '수', 3: '목', 4: '금', 5: '토', 6: '일'}


# ==============================================================================
# 1. 유틸리티 함수 (두 번째 코드의 간결한 이름 사용)
# ==============================================================================

def has_kr(s):
    """문자열에 한글이 포함되어 있는지 확인합니다."""
    return any(0xAC00 <= ord(c) <= 0xD7A3 for c in s)


def fix_icon(code):
    """아이콘 코드를 낮/일반 구름으로 통일합니다."""
    if not code:
        return code
    if code.endswith("n"):
        code = code.replace("n", "d")
    if code == "04d":
        return "03d"
    return code


def init_state():
    """세션 상태를 초기화합니다."""
    ss = st.session_state
    ss.setdefault("searched", False)
    ss.setdefault("data", None)


# ==============================================================================
# 2. 데이터 페치 함수 (load_weather 사용)
# ==============================================================================

def load_weather(city):
    """날씨 및 미세먼지 데이터를 API에서 가져와 세션 상태에 저장합니다."""
    ss = st.session_state
    if not API_KEY:
        st.error("API Key가 설정되어 있지 않습니다.")
        return

    q = f"{city},KR" if has_kr(city) else city

    # GeoCoding
    geo = requests.get(GEO_URL, params={"q": q, "limit": 1, "appid": API_KEY}).json()
    if not geo:
        st.error(f"'{city}' 지역을 찾을 수 없습니다.")
        ss.searched = False
        return

    lat, lon = geo[0]["lat"], geo[0]["lon"]
    name_kr = geo[0].get("local_names", {}).get("ko", city)

    # Weather
    w = requests.get(BASE_URL, params={
        "lat": lat, "lon": lon, "appid": API_KEY,
        "units": "metric", "lang": "en"
    }).json()

    # Air Pollution
    air = requests.get(AIR_URL, params={
        "lat": lat, "lon": lon, "appid": API_KEY
    }).json()

    ss.data = {"name": name_kr, "lat": lat, "lon": lon, "w": w, "air": air}
    ss.searched = True
    st.rerun()


# ==============================================================================
# 3. 데이터 처리 및 분석 함수 (Pandas, UI 테이블 생성을 위한 로직)
# ==============================================================================

def process_data(w):
    """예보 데이터를 DataFrame으로 변환하고 일별 요약을 생성합니다."""
    
    # 3시간 간격 전체 데이터프레임 (df)
    df = pd.DataFrame(
        [{
            'dt': pd.to_datetime(item['dt_txt']).tz_localize('UTC').tz_convert('Asia/Seoul'),
            'temp': item['main']['temp'],
            'feel': item['main']['feels_like'],
            '최저_raw': item['main']['temp_min'],
            '최고_raw': item['main']['temp_max'],
            'icon': item['weather'][0]['icon'],
            '강수': item['pop'] * 100
        } for item in w['list']]
    )

    # 일별 요약 데이터프레임 (daily)
    daily = df.groupby(df['dt'].dt.date).agg(
        최고=('최고_raw', np.max),
        최저=('최저_raw', np.min),
        대표=('icon', lambda x: x.mode()[0]), # 최빈값 (가장 흔한 아이콘)
        강수=('강수', np.mean)
    ).reset_index().rename(columns={'dt': '날짜'})

    # 날짜 라벨(오늘/내일/요일) 추가
    today = datetime.datetime.now().date()
    daily['강수'] = daily['강수'].round(0)
    daily['요일'] = daily['날짜'].apply(lambda x:
                                       '오늘' if x == today else
                                       '내일' if x == today + datetime.timedelta(days=1) else
                                       KR_WEEKDAYS[x.weekday()])

    return df, daily


def weekly_summary(daily, air):
    """
    일별 요약 및 현재 대기질 정보를 바탕으로 주간 날씨 조언을 생성합니다. (UI 조언 텍스트 유지를 위해 상세 로직 사용)
    """
    avg_max = daily["최고"].mean()
    msg = []
    
    # 1. 온도 분석
    if avg_max >= 27:
        msg.append("이번 주는 **날이 더워요**. 반팔이나 시원한 옷을 입어주세요. 🥵")
    elif 16 <= avg_max < 27:
        msg.append("이번 주는 **활동하기 좋은 날씨**예요. 가벼운 겉옷은 선택사항입니다. 😊")
    elif 5 <= avg_max < 16:
        msg.append("이번 주는 **날이 쌀쌀해요**. 긴팔이나 외투를 챙기는 것이 좋을 거예요. 🧥")
    else:
        msg.append("이번 주는 **날이 추워요**. 따뜻하고 두꺼운 외투와 방한용품을 챙겨주세요. 🥶")

    # 2. 일교차 분석
    daily["일교차"] = daily["최고"] - daily["최저"]
    d = daily["일교차"].mean()
    if d >= 10:
        msg.append(f"🌡️ **일교차가 평균 {d:.1f}°C**로 매우 커요. 얇은 옷을 여러 겹 껴입어 체온 조절에 신경 써주세요.")

    # 3. 강수 분석
    rain_days = (daily["강수"] >= 50).sum()
    if rain_days >= len(daily) / 2:
        msg.append("🌧️ **비 또는 눈 소식이 잦아요**. 외출 시 꼭 우산을 챙겨주세요.")

    # 4. 대기질 분석
    air_advice = ""
    if air and "list" in air:
        aqi = air["list"][0]["main"]["aqi"]
        txt, _ = AQI_TEXT.get(aqi, ("알 수 없음", "❓"))
        
        if aqi >= 3:
            air_advice = f"😷 현재 **대기 질이 '{txt}' 수준**이에요. 외출 시 KF94 마스크를 챙겨주세요."
            msg.append(air_advice)
        
    # 5. 추가 조언 (날씨 좋을 때)
    if not air_advice and rain_days == 0 and 16 <= avg_max < 27:
        msg.append("☀️ **맑고 좋은 날씨**가 예상되니, 즐거운 한 주 보내세요!")
        
    return "\n\n".join(msg)


# ==============================================================================
# 4. Streamlit UI
# ==============================================================================

init_state()
ss = st.session_state

st.title("국내 날씨 및 미세먼지 예보 🌤️💨")
st.markdown("---")

if not ss.searched:
    # --- 검색 전 초기 화면 ---
    city_in = st.text_input("지명 입력", "서울")
    if st.button("날씨 및 미세먼지 정보 가져오기 (검색)"): # 첫 번째 코드의 버튼 텍스트 사용
        if city_in:
            load_weather(city_in)
        else:
            st.warning("도시 이름을 입력해 주세요.")
else:
    # --- 검색 후 대시보드 화면 ---
    data = ss.data
    w = data["w"]
    air = data["air"]
    city = data["name"]
    lat, lon = data["lat"], data["lon"]
    
    # 데이터 처리
    df, daily = process_data(w)

    # 1. 상단 현재 날씨 정보
    st.markdown(f"## {city}")

    now = w["list"][0]
    t = now["main"]["temp"]
    fl = now["main"]["feels_like"]
    desc_en = now["weather"][0]["description"]
    desc_kr = W_DESC.get(desc_en, desc_en)
    icon = fix_icon(now["weather"][0]["icon"])
    
    # 24시간 최고/최저 온도 (UI 유지를 위해 df가 아닌 list[:8] 사용)
    tlist = w["list"][:8]
    tmin = min(x["main"]["temp_min"] for x in tlist)
    tmax = max(x["main"]["temp_max"] for x in tlist)

    # 시간 포맷팅 (첫 번째 코드의 상세 포맷 유지)
    dt_utc = pd.to_datetime(now['dt_txt']).tz_localize('UTC')
    weekday_kr = KR_WEEKDAYS[dt_utc.tz_convert('Asia/Seoul').weekday()]
    time_date = dt_utc.tz_convert('Asia/Seoul').strftime('%m월 %d일')
    time_time = dt_utc.tz_convert('Asia/Seoul').strftime('오후 %I:%M')
    display_time = f"{time_date} {weekday_kr}요일, {time_time}"

    st.markdown(f"""
    <div style="display: flex; align-items: center; justify-content: flex-start; gap: 20px;">
        <h1 style="font-size: 5em; margin: 0;">{t:.0f}°</h1>
        <img src="http://openweathermap.org/img/wn/{icon}@2x.png" alt="날씨 아이콘" style="width: 100px; height: 100px;"/>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"**{desc_kr}**")
    st.markdown(f"⬆️{tmax:.0f}° / ⬇️{tmin:.0f}°")
    st.markdown(f"체감온도 {fl:.0f}°")
    st.markdown(f"{display_time}")
    st.markdown("---")

    # 2. 시간별 예보
    st.markdown("### ⏰ 시간별 예보")
    cols = st.columns(len(tlist))
    for i, item in enumerate(tlist):
        with cols[i]:
            kst_time = pd.to_datetime(item["dt_txt"]).tz_localize('UTC').tz_convert('Asia/Seoul').strftime('%H시')
            ti = item["main"]["temp"]
            p = item["pop"] * 100
            ic = fix_icon(item["weather"][0]["icon"])
            st.markdown(f"""
            <div style="text-align: center; padding: 5px;">
                <p style="font-weight: bold; margin-bottom: 5px;">{kst_time}</p>
                <img src="http://openweathermap.org/img/wn/{ic}.png" alt="날씨 아이콘" style="width: 40px; height: 40px;"/>
                <p style="font-size: 1.1em; margin-top: 5px; margin-bottom: 5px;">{ti:.0f}°</p>
                <p style="font-size: 0.8em; color: #888; margin: 0;">💧 {p:.0f}%</p>
            </div>
            """, unsafe_allow_html=True)
    st.markdown("---")

    # 3. 미세먼지 정보
    st.markdown("### 💨 현재 대기 질 정보")
    if air and "list" in air:
        info = air["list"][0]
        aqi = info["main"]["aqi"]
        txt, em = AQI_TEXT.get(aqi, ("?", ""))
        pm25 = info["components"].get("pm2_5", 0)
        pm10 = info["components"].get("pm10", 0)

        # 첫 번째 코드의 상세 HTML 레이아웃 유지
        st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px;">
            <div style="text-align: center;">
                <p style="margin:0; font-size: 1.2em;">AQI {em}</p>
                <p style="margin:0; font-weight: bold;">{txt}</p>
            </div>
            <div style="text-align: center;">
                <p style="margin:0; font-size: 0.9em;">PM2.5</p>
                <p style="margin:0; font-weight: bold;">{pm25:.1f} &micro;g/m&sup3;</p> 
            </div>
            <div style="text-align: center;">
                <p style="margin:0; font-size: 0.9em;">PM10</p>
                <p style="margin:0; font-weight: bold;">{pm10:.1f} &micro;g/m&sup3;</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("미세먼지 정보를 가져오는 데 실패했습니다.")
    st.markdown("---")

    # 4. 일별 요약 (주간 예보)
    st.markdown("### 📅 주간 날씨 예보")
    
    # 첫 번째 코드의 상세 테이블 헤더 UI 유지
    st.markdown(f"""
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 2px solid #333; margin-bottom: 5px; font-weight: bold; color: #000; font-size: 1.2em;">
        <div style="width: 15%; text-align: center;">요일</div>
        <div style="width: 15%; text-align: center;">강수확률</div>
        <div style="width: 20%; text-align: center;">날씨</div>
        <div style="width: 25%; text-align: center;">최고 온도</div>
        <div style="width: 25%; text-align: center;">최저 온도</div>
    </div>
    """, unsafe_allow_html=True)

    for _, r in daily.iterrows():
        ic = fix_icon(r["대표"])
        day_label = r['요일']
        max_t = r['최고']
        min_t = r['최저']
        avg_pop = r['강수']
        
        # 첫 번째 코드의 상세 테이블 행 UI 유지
        st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 0; color: #000; font-size: 1.1em;">
            <div style="width: 15%; font-weight: bold; text-align: center;">{day_label}</div>
            <div style="width: 15%; text-align: center;">💧 {avg_pop:.0f}%</div>
            <div style="width: 20%; text-align: center;">
                <img src="http://openweathermap.org/img/wn/{ic}.png" alt="날씨 아이콘" style="width: 50px; height: 50px;"/>
            </div>
            <div style="width: 25%; text-align: center; font-weight: bold; font-size: 1.2em;">{max_t:.0f}°</div>
            <div style="width: 25%; text-align: center; font-weight: bold; font-size: 1.2em;">{min_t:.0f}°</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")

    # 5. 5일 온도 변화 그래프
    st.markdown("### 📈 5일 온도 변화 그래프")
    
    fig = go.Figure()
    # df의 간결한 컬럼명 ('temp', 'feel') 사용
    fig.add_trace(go.Scatter(x=df["dt"], y=df["temp"], 
                             mode='lines+markers', name='예상온도 (°C)', line=dict(color='orange')))
    fig.add_trace(go.Scatter(x=df["dt"], y=df["feel"], 
                             mode='lines+markers', name='체감온도 (°C)', line=dict(color='blue', dash='dot')))
    fig.update_layout(
        xaxis=dict(title="날짜", tickformat="%m-%d", tickangle=0,),
        yaxis_title="온도 (°C)", hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=30, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("---")

    # 6. 주간 날씨 분석 및 조언
    st.markdown("### 💡 이번 주 날씨 조언")
    st.info(weekly_summary(daily, air))
    st.markdown("---")

    # 7. 다른 지역 검색
    st.markdown("### 📍 다른 지역 검색")
    new_city = st.text_input("새로운 지명 입력", city, key="new_city_input") # 첫 번째 코드의 라벨 사용
    if st.button("날씨 정보 다시 가져오기"): # 첫 번째 코드의 버튼 텍스트 사용
        if new_city:
            load_weather(new_city)
        else:
            st.warning("도시 이름을 입력해 주세요.")

    # 8. 현재 위치 지도
    st.markdown("### 🗺️ 현재 위치 지도")
    st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}), zoom=10)
    st.caption(f"**지도 중심 위치:** 위도 {lat:.2f}, 경도 {lon:.2f}")
