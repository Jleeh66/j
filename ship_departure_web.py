"""선박 출항 판단 웹 앱 (Python 표준 라이브러리만 사용)."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen
import json

HOST, PORT = "127.0.0.1", 8000

PAGE = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>선박 출항 판단기</title>
<style>*{box-sizing:border-box}body{margin:0;background:#eef4f7;color:#17324d;font-family:Arial,"Malgun Gothic",sans-serif}
header{background:linear-gradient(120deg,#073b5c,#087e8b);color:#fff;padding:32px 20px;text-align:center}h1{margin:0 0 8px}
main{max-width:760px;margin:28px auto;padding:0 16px}.card{background:#fff;border-radius:16px;padding:26px;box-shadow:0 8px 28px #1233}
.grid,.checks{display:grid;grid-template-columns:1fr 1fr;gap:18px}label{display:block;font-weight:bold;margin-bottom:7px}
input[type=number],input[type=text]{width:100%;padding:12px;border:1px solid #b8c8d1;border-radius:8px;font-size:16px}
.weather-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:18px 0}.weather-card{background:#eef6f8;border-radius:10px;padding:14px;text-align:center}.weather-card strong{display:block;font-size:20px;margin-top:6px}
fieldset{border:1px solid #d1dde3;border-radius:10px;margin:22px 0;padding:15px}legend{font-weight:bold}.checks label{font-weight:normal}
button{width:100%;padding:14px;border:0;border-radius:9px;background:#087e8b;color:#fff;font-size:17px;font-weight:bold;cursor:pointer}
#result{display:none;margin-top:20px;padding:18px;border-radius:10px}.ok{background:#e5f7ed;color:#176b3a}.warn{background:#fff4d8;color:#805b00}.no{background:#fde7e7;color:#9c2424}
.report{margin:12px 0;line-height:1.7;white-space:pre-line}.note{font-size:13px;line-height:1.5;color:#5c6e78;margin-top:18px}@media(max-width:600px){.grid,.checks{grid-template-columns:1fr}}</style></head>
<body><header><h1>⚓ 선박 출항 판단기</h1><div>기상 및 선박 상태 기반 의사결정 보조</div></header><main><div class="card">
<form id="f"><div class="grid"><div><label>선박명</label><input name="vessel_name" type="text" maxlength="50" placeholder="예: 한라호" required></div>
<div><label>지역</label><input name="location" type="text" maxlength="50" value="부산항" placeholder="예: 부산항, 인천, 제주" required></div>
<div><label>선박 길이 (m)</label><input name="length" type="number" min="1" step=".1" value="20" required></div></div>
<input name="wind" type="hidden"><input name="wave" type="hidden"><input name="visibility" type="hidden">
<div class="weather-grid"><div class="weather-card">풍속<strong id="windView">-</strong></div><div class="weather-card">파고<strong id="waveView">-</strong></div><div class="weather-card">시정<strong id="visibilityView">-</strong></div></div>
<fieldset><legend>선박 및 운항 상태</legend><div class="checks">
<label><input name="engine" type="checkbox" checked> 기관 정상</label><label><input name="navigation" type="checkbox" checked> 항해 장비 정상</label>
<label><input name="lifesaving" type="checkbox" checked> 구명 장비 정상</label><label><input name="crew" type="checkbox" checked> 승무원 준비 완료</label>
<label><input name="warning" type="checkbox"> 기상특보 발효 중</label></div></fieldset>
<button id="weatherBtn" type="button">기상 조회 후 출항 판단</button><div id="weatherStatus" class="note"></div><div id="result"><h2 id="decision"></h2><div id="summary" class="report"></div><span id="reasons"></span></div>
<p class="note">※ 교육용 예시입니다. 실제 출항은 최신 기상정보, 관할 법규와 선장·운항관리자의 승인을 따르세요.</p></form></div></main>
<script>weatherBtn.onclick=async()=>{if(!f.reportValidity())return;weatherBtn.disabled=true;weatherStatus.textContent='지역과 기상 정보를 불러오는 중...';try{let r=await fetch(`/weather?location=${encodeURIComponent(f.location.value)}`),d=await r.json();if(!r.ok)throw Error(d.error);f.wind.value=d.wind_speed_ms;f.wave.value=d.wave_height_m;f.visibility.value=d.visibility_km;windView.textContent=d.wind_speed_ms+' m/s';waveView.textContent=d.wave_height_m+' m';visibilityView.textContent=d.visibility_km+' km';weatherStatus.textContent=`${d.resolved_name} · ${d.observed_at} 기준 예보`;f.requestSubmit()}catch(e){weatherStatus.textContent='기상 조회 실패: '+e.message}finally{weatherBtn.disabled=false}};
f.onsubmit=async e=>{e.preventDefault();let r=await fetch('/assess',{method:'POST',body:new URLSearchParams(new FormData(f))});let d=await r.json();
result.style.display='block';result.className=d.decision==='출항 가능'?'ok':d.decision==='조건부 가능'?'warn':'no';decision.textContent=(d.vessel_name?d.vessel_name+' — ':'')+d.decision;summary.textContent=`점검 일시: ${new Date().toLocaleString('ko-KR')}\n지역: ${f.location.value}\n풍속: ${f.wind.value} m/s  |  파고: ${f.wave.value} m\n시정: ${f.visibility.value} km  |  선박 길이: ${f.length.value} m`;reasons.textContent='판정 사유: '+d.reasons.join(', ')}</script></body></html>'''


def assess(d):
    vessel_name = d.get("vessel_name", [""])[0].strip()
    if not vessel_name: raise ValueError("선박명을 입력하세요")
    wind, wave = float(d["wind"][0]), float(d["wave"][0])
    visibility, length = float(d["visibility"][0]), float(d["length"][0])
    if min(wind, wave, visibility) < 0 or length < 1:
        raise ValueError("입력값 범위를 확인하세요")
    no, warn = [], []
    checks = [("기관 상태 불량", "engine"), ("항해 장비 상태 불량", "navigation"),
              ("구명 장비 상태 불량", "lifesaving"), ("승무원 준비 미완료", "crew")]
    no += [reason for reason, key in checks if key not in d]
    if "warning" in d: no.append("기상특보 발효")
    if wind > 14: no.append(f"풍속 초과 ({wind:g} > 14 m/s)")
    elif wind >= 10: warn.append(f"강한 바람 ({wind:g} m/s)")
    if wave > 3: no.append(f"파고 초과 ({wave:g} > 3 m)")
    elif wave >= 2: warn.append(f"높은 파고 ({wave:g} m)")
    if visibility < .5: no.append(f"시정 부족 ({visibility:g} < 0.5 km)")
    elif visibility <= 1: warn.append(f"낮은 시정 ({visibility:g} km)")
    if no: return {"vessel_name": vessel_name, "decision": "출항 불가", "reasons": no}
    if warn: return {"vessel_name": vessel_name, "decision": "조건부 가능", "reasons": warn}
    return {"vessel_name": vessel_name, "decision": "출항 가능", "reasons": ["설정된 모든 기준 충족"]}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/weather":
            try:
                q = parse_qs(parsed.query); name = q.get("location", [""])[0]
                lat, lon, resolved = geocode(name)
                result = get_weather(lat, lon); result["resolved_name"] = resolved
                self.send_body(200, json.dumps(result, ensure_ascii=False).encode(), "application/json; charset=utf-8")
            except Exception as e:
                self.send_body(502, json.dumps({"error": str(e)}, ensure_ascii=False).encode(), "application/json; charset=utf-8")
            return
        if parsed.path != "/": return self.send_error(404)
        self.send_body(200, PAGE.encode(), "text/html; charset=utf-8")
    def do_POST(self):
        if self.path != "/assess": return self.send_error(404)
        try:
            size = int(self.headers.get("Content-Length", 0))
            result = assess(parse_qs(self.rfile.read(size).decode()))
            self.send_body(200, json.dumps(result, ensure_ascii=False).encode(), "application/json; charset=utf-8")
        except (KeyError, ValueError) as e:
            self.send_body(400, json.dumps({"decision":"입력 오류","reasons":[str(e)]}, ensure_ascii=False).encode(), "application/json; charset=utf-8")
    def send_body(self, code, body, content_type):
        self.send_response(code); self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(body)); self.end_headers(); self.wfile.write(body)
    def log_message(self, *_): pass


def get_weather(lat, lon):
    if not -90 <= lat <= 90 or not -180 <= lon <= 180: raise ValueError("위도·경도를 확인하세요")
    common = {"latitude": lat, "longitude": lon, "timezone": "Asia/Seoul"}
    weather_url = "https://api.open-meteo.com/v1/forecast?" + urlencode({**common, "current": "wind_speed_10m,visibility", "wind_speed_unit": "ms"})
    with urlopen(weather_url, timeout=10) as r: weather = json.load(r)["current"]
    marine = None
    for dlat, dlon in ((0, 0), (0, .05), (0, -.05), (.05, 0), (-.05, 0), (0, .1), (0, -.1)):
        marine_url = "https://marine-api.open-meteo.com/v1/marine?" + urlencode({**common, "latitude": lat+dlat, "longitude": lon+dlon, "current": "wave_height", "cell_selection": "sea"})
        with urlopen(marine_url, timeout=10) as r: candidate = json.load(r).get("current", {})
        if candidate.get("wave_height") is not None: marine = candidate; break
    if marine is None: raise ValueError("해당 지역 인근의 파고 정보가 없습니다")
    return {"wind_speed_ms": round(weather["wind_speed_10m"], 1), "wave_height_m": round(marine["wave_height"], 1),
            "visibility_km": round(weather["visibility"] / 1000, 1), "observed_at": weather["time"], "source": "Open-Meteo"}


def geocode(name):
    name = name.strip()
    if len(name) < 2: raise ValueError("지역명을 두 글자 이상 입력하세요")
    ports = {"부산": (35.10,129.04), "인천": (37.45,126.60), "제주": (33.52,126.53), "목포": (34.78,126.38),
             "여수": (34.74,127.75), "울산": (35.50,129.39), "포항": (36.04,129.38), "군산": (35.98,126.58),
             "속초": (38.21,128.60), "동해": (37.50,129.14), "통영": (34.84,128.43), "거제": (34.88,128.62)}
    key = name.removesuffix("항").removesuffix("시")
    if key in ports: return *ports[key], key + "항"
    for query in (name, name[:-1] if name.endswith("항") else name):
        url = "https://geocoding-api.open-meteo.com/v1/search?" + urlencode({"name": query, "count": 1, "language": "ko", "countryCode": "KR"})
        with urlopen(url, timeout=10) as r: results = json.load(r).get("results", [])
        if results:
            place = results[0]; label = ", ".join(filter(None, [place["name"], place.get("admin1")]))
            return place["latitude"], place["longitude"], label
    raise ValueError("지역을 찾을 수 없습니다")


if __name__ == "__main__":
    print(f"브라우저에서 http://{HOST}:{PORT} 을 여세요. 종료: Ctrl+C")
    try: ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt: print("\n서버를 종료합니다.")
