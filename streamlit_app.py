"""선박 출항 판단기 - Streamlit Community Cloud 배포용."""
import json
from urllib.parse import urlencode
from urllib.request import urlopen

import streamlit as st


PORTS = {
    "부산": (35.10, 129.04), "인천": (37.45, 126.60), "제주": (33.52, 126.53),
    "목포": (34.78, 126.38), "여수": (34.74, 127.75), "울산": (35.50, 129.39),
    "포항": (36.04, 129.38), "군산": (35.98, 126.58), "속초": (38.21, 128.60),
    "동해": (37.50, 129.14), "통영": (34.84, 128.43), "거제": (34.88, 128.62),
}


def geocode(name: str) -> tuple[float, float, str]:
    name = name.strip()
    if len(name) < 2:
        raise ValueError("지역명을 두 글자 이상 입력하세요.")
    key = name.removesuffix("항").removesuffix("시")
    if key in PORTS:
        return *PORTS[key], key + "항"
    for query in (name, name[:-1] if name.endswith("항") else name):
        url = "https://geocoding-api.open-meteo.com/v1/search?" + urlencode(
            {"name": query, "count": 1, "language": "ko"}
        )
        with urlopen(url, timeout=10) as response:
            results = json.load(response).get("results", [])
        if results:
            place = results[0]
            label = ", ".join(filter(None, [place["name"], place.get("admin1"), place.get("country")]))
            return place["latitude"], place["longitude"], label
    raise ValueError("지역을 찾을 수 없습니다.")


def get_weather(lat: float, lon: float) -> dict:
    common = {"latitude": lat, "longitude": lon, "timezone": "auto"}
    weather_url = "https://api.open-meteo.com/v1/forecast?" + urlencode(
        {**common, "current": "wind_speed_10m,visibility", "wind_speed_unit": "ms"}
    )
    with urlopen(weather_url, timeout=10) as response:
        weather = json.load(response)["current"]

    marine = None
    for dlat, dlon in ((0, 0), (0, .05), (0, -.05), (.05, 0), (-.05, 0), (0, .1), (0, -.1)):
        marine_url = "https://marine-api.open-meteo.com/v1/marine?" + urlencode(
            {**common, "latitude": lat + dlat, "longitude": lon + dlon,
             "current": "wave_height", "cell_selection": "sea"}
        )
        with urlopen(marine_url, timeout=10) as response:
            candidate = json.load(response).get("current", {})
        if candidate.get("wave_height") is not None:
            marine = candidate
            break
    if marine is None:
        raise ValueError("해당 지역 인근의 파고 정보가 없습니다.")
    return {
        "wind": round(weather["wind_speed_10m"], 1),
        "wave": round(marine["wave_height"], 1),
        "visibility": round(weather["visibility"] / 1000, 1),
        "time": weather["time"],
    }


def assess(wind, wave, visibility, engine, navigation, lifesaving, crew, warning):
    prohibited, caution = [], []
    for reason, ok in [("기관 상태 불량", engine), ("항해 장비 상태 불량", navigation),
                       ("구명 장비 상태 불량", lifesaving), ("승무원 준비 미완료", crew)]:
        if not ok:
            prohibited.append(reason)
    if warning:
        prohibited.append("기상특보 발효")
    if wind > 14:
        prohibited.append(f"풍속 초과 ({wind:g} > 14 m/s)")
    elif wind >= 10:
        caution.append(f"강한 바람 ({wind:g} m/s)")
    if wave > 3:
        prohibited.append(f"파고 초과 ({wave:g} > 3 m)")
    elif wave >= 2:
        caution.append(f"높은 파고 ({wave:g} m)")
    if visibility < .5:
        prohibited.append(f"시정 부족 ({visibility:g} < 0.5 km)")
    elif visibility <= 1:
        caution.append(f"낮은 시정 ({visibility:g} km)")
    if prohibited:
        return "출항 불가", prohibited
    if caution:
        return "조건부 가능", caution
    return "출항 가능", ["설정된 모든 기준 충족"]


st.set_page_config(page_title="선박 출항 판단기", page_icon="⚓", layout="centered")
st.title("⚓ 선박 출항 판단기")
st.caption("기상 및 선박 상태 기반 의사결정 보조")

with st.form("voyage_form"):
    vessel_name = st.text_input("선박명", placeholder="예: 한라호")
    location = st.text_input("지역", value="부산항", placeholder="예: 부산항, Yokohama, Singapore")
    vessel_length = st.number_input("선박 길이 (m)", min_value=1.0, value=20.0, step=0.1)
    st.subheader("선박 및 운항 상태")
    col1, col2 = st.columns(2)
    with col1:
        engine = st.checkbox("기관 정상", value=True)
        lifesaving = st.checkbox("구명 장비 정상", value=True)
    with col2:
        navigation = st.checkbox("항해 장비 정상", value=True)
        crew = st.checkbox("승무원 준비 완료", value=True)
    warning = st.checkbox("기상특보 발효 중")
    submitted = st.form_submit_button("기상 조회 후 출항 판단", use_container_width=True)

if submitted:
    if not vessel_name.strip():
        st.error("선박명을 입력하세요.")
    else:
        try:
            with st.spinner("지역과 기상 정보를 조회하고 있습니다..."):
                lat, lon, resolved = geocode(location)
                weather = get_weather(lat, lon)
            st.caption(f"{resolved} · {weather['time']} 기준 Open-Meteo 예보")
            c1, c2, c3 = st.columns(3)
            c1.metric("풍속", f"{weather['wind']} m/s")
            c2.metric("파고", f"{weather['wave']} m")
            c3.metric("시정", f"{weather['visibility']} km")
            decision, reasons = assess(weather["wind"], weather["wave"], weather["visibility"],
                                       engine, navigation, lifesaving, crew, warning)
            message = f"{vessel_name} — {decision}\n\n판정 사유: {', '.join(reasons)}"
            if decision == "출항 가능":
                st.success(message)
            elif decision == "조건부 가능":
                st.warning(message)
            else:
                st.error(message)
        except Exception as exc:
            st.error(f"기상 조회 실패: {exc}")

st.divider()
st.caption("교육용 예시입니다. 실제 출항은 최신 공식 기상정보, 관할 법규 및 선장·운항관리자의 승인을 따르세요.")
st.caption("Weather data: Open-Meteo · Marine models are not a substitute for nautical navigation data.")
