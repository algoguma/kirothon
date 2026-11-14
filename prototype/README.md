# 💬 내 말투 남자친구 (Kirothon)

카카오톡 대화 파일(**txt** 또는 **JSON**)을 넣으면 **Qwen3.8-27B**가
1. 최근 대화에서 **내 말투**를 분석해 `style.md`로 저장하고
2. 전체 대화에서 **우리의 기억**(약속, 계획, 있었던 일, 상대 정보)을 뽑아 `memory.md`로 저장하고
3. 두 md 파일을 프롬프트로 받아, **내 말투로 기억을 이어가는 남자친구**로 대답합니다.

> 예) 과거에 "경주 가서 재모식당 가자"고 했다면 → "경주가서 점심 어디서 먹기로 했지??" → "재모식당이요 ㅎㅎ"

그리고 메시지가 올 때마다 Qwen3.8이 **두 가지를 판단해 나(주인)에게 알려줍니다.**
- 🚨 **비상상황**: 상대가 아프거나, 다쳤거나, 위험하면 → 주인 패널에 심각도(낮음/중간/높음)와 함께 알림 (`alerts.jsonl` 기록). 답장은 장난 없이 진지하게 해요.
- ❓ **기억에 없는 질문**: 지어내야만 답할 수 있으면 → 챗봇은 "잠깐만 확인해보고 알려줄게"로 보류하고 주인에게 질문해요. 주인이 답하면 내 말투로 바꿔 전달하고 `memory.md`에 저장해서, 다음부터는 바로 답해요.

```
여친> 오빠 다음주 금요일에 시간 돼? 우리 엄마가 저녁 같이 먹재
봇>   아 진짜? / 잠깐만 확인해보고 알려줄게          ← ❓ 주인 패널: "수락할까요?"
[주인] 금요일 저녁 7시 괜찮아, 어머님 좋아하시는 한식집으로 내가 예약할게
봇>   확인해봤는데 / 금요일 저녁 7시 괜찮아 / 어머님 좋아하시는 한식집으로 내가 예약할게
여친> 오빠 그럼 금요일에 몇시에 보는거야?
봇>   7시에 / 어머님이랑 만나기로 했잖아               ← memory.md에서 기억
```

모든 추론은 원격 GPU 서버의 **vLLM + Qwen3.8**에서만 일어납니다. 외부 상용 API는 쓰지 않습니다.

## 구조

```
대화 txt/JSON ──▶ parser.py ──▶ 앞 1000개 메시지
                              │
              ┌───────────────┴────────────────┐   (Qwen3.8 병렬 호출)
              ▼                                ▼
   style.py: 최근 500개로 말투 분석     memory.py: 1000개를 250개씩 4구간
              │                         → 구간별 기억 추출 → 하나로 병합
              ▼                                ▼
   output/<파일>_<내이름>/style.md     output/<파일>_<내이름>/memory.md
              └───────────────┬────────────────┘
                              ▼
  persona.py: 시스템 프롬프트 = <말투> style.md + <기억> memory.md + 최근 원문 150개
                              ▼
          Qwen3.8 (vLLM) ──▶ 카톡처럼 짧게 끊어진 답장
```

| 파일 | 역할 |
|---|---|
| `boyfriend/parser.py` | 대화 파일 파싱. 카톡 txt(PC/모바일, 여러 줄 메시지)와 JSON(텔레그램 내보내기 형식, `{"messages": [...]}` 또는 `[...]`)을 자동으로 구분하고, 사진/이모티콘/서비스 메시지는 제외 |
| `boyfriend/style.py` | Qwen3.8로 말투 분석 → `style.md` (호칭, 어미, 웃음, 기호, 오타 습관, 예시 문장) |
| `boyfriend/memory.py` | Qwen3.8로 기억 추출 → `memory.md` (약속/계획, 사건, 상대·나에 대한 사실, 인물, 장소, 농담, 미해결 얘기) |
| `boyfriend/pipeline.py` | 말투 분석과 기억 추출을 동시 실행, md 저장 및 불러오기 |
| `boyfriend/checker.py` | 메시지마다 Qwen3.8로 🚨비상상황 / ❓주인 확인 필요 판단 (JSON) |
| `boyfriend/persona.py` | style.md와 memory.md를 프롬프트로 남자친구 대화, 판단 결과에 따라 톤 조절/보류, 주인 답변 전달 및 기억 저장 |
| `boyfriend/llm.py` | vLLM OpenAI 호환 API 클라이언트 (thinking 모드 제어, JSON 모드) |
| `boyfriend/tunnel.py` | `.env`의 `SSH_TUNNEL`로 vLLM 서버 SSH 터널 자동 연결/종료 |
| `run.py` / `run.sh` | **해커톤 실행 파일**: 대화 파일(txt/JSON) + 내 이름 + 상대 메시지 → JSON |
| `main.py` | 터미널 챗봇 |
| `app.py` | Gradio 웹 데모 (md 확인, 수정, 적용 가능) |
| `server/serve.sh` | GPU 서버의 vLLM 실행 스크립트 |

## 실행

### 1. 서버 (GPU)
```bash
bash server/serve.sh      # Qwen3.8-27B → 127.0.0.1:8000
```

### 2. 로컬
```bash

pip install -r requirements.txt
cp .env.example .env   # SSH_TUNNEL=<user>@<server> 설정 → 실행 시 터널 자동 연결

# 웹 데모
python app.py          # http://localhost:7860

# 또는 터미널
python main.py /path/to/Talk.txt                 # 분석(1~2분) → output/Talk_<내이름>/ 에 md 저장 → 대화
python main.py /path/to/Talk.txt --me 내이름
python main.py --load output/Talk_홍길동         # 저장된 style.md / memory.md로 바로 대화
```

분석 결과는 **대화 파일 + 내 이름** 기준으로 `output/<파일>_<내이름>/`에 저장되고(JSON은 `output/<파일>_json_<내이름>/`), 다음부터는 분석 없이 불러와서 바로 대화합니다.
- 웹: 파일을 올리면 저장된 분석이 있는지 알려주고, **"💾 저장된 분석 불러오기"** 버튼으로 즉시 시작 (다시 분석하고 싶을 때만 "새로 분석")
- 터미널: `--load output/<파일>_<내이름>`

`style.md`, `memory.md`는 사람이 읽고 직접 고칠 수 있고, 고친 내용이 그대로 프롬프트에 들어갑니다. 웹 데모에서는 탭에서 고친 뒤 "적용"을 누르면 됩니다.

## 🏁 해커톤 실행 파일 (JSON 출력)

입력: **대화 파일(txt/JSON) + 대화 속 내 이름 + 상대 메시지** → 출력: **JSON (답변, 비상 여부, 확인필요 여부)**

```bash
./run.sh --talk Talk.txt --me 홍길동 --message "오빠 다음주 금요일에 시간 돼?"
./run.sh --talk Talk.txt --me 홍길동 -m "오빠 뭐해??" -m "나 목 아파ㅜㅜ"   # 여러 개 → JSON 배열 (대화 이어짐)
cat messages.txt | ./run.sh --talk Talk.txt --me 홍길동                 # 표준입력 → 한 줄에 JSON 하나 (JSONL)
./run.sh --talk Talk.json --me 홍길동 -m "오빠 뭐해??"                 # JSON 대화 파일도 동일
```

**표준입력 모드 = 대화 기억 모드**: 프로세스가 켜져 있는 동안 주고받은 대화를 기억하고 참조해요(최근 30턴). `/reset`을 보내면 초기화돼요.
```
[1] 나 오늘 점심에 엽떡 먹었어 ㅎㅎ      → 와 엽떡?? / 오늘 갑자기 땡겼어?
[2] 근데 너무 매워서 배 아파ㅜㅜ (🚨)    → 아이고... / 괜찮아?? / 지금 바로 물이나 우유 좀 마셔
[3] 내가 오늘 점심에 뭐 먹었다고 했지?   → 엽떡이지 / 그거 맞잖아 ㅎㅎ
```
다른 프로그램에서 연결할 때는 프로세스를 하나 켜두고 한 줄씩 보내면 돼요.
```python
import json, subprocess
p = subprocess.Popen(["./run.sh", "--talk", "Talk.txt", "--me", "홍길동"],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
def send(msg):
    p.stdin.write(msg + "\n"); p.stdin.flush()
    return json.loads(p.stdout.readline())
print(send("나 오늘 엽떡 먹었어")["reply"])
print(send("내가 뭐 먹었다고 했지?")["reply"])   # 앞 대화를 기억해요
```
- 처음 실행할 때만 말투/기억을 분석해요 (약 2분, `output/<파일>_<내이름>/`에 저장). 이후에는 바로 답해요. 새로 분석하려면 `--reanalyze`를 붙이세요.
- 설정 파일은 `--env 경로`로 지정할 수 있어요 (기본: 프로젝트 폴더의 `.env`). 예) `./run.sh --env ~/secrets/kirothon.env --talk Talk.txt --me 홍길동`. 지정한 파일이 없으면 `{"error": ...}`를 출력해요.
- **stdout에는 JSON만** 출력하고, 진행 로그는 stderr로 보내요. 보기 좋게 출력하려면 `--pretty`를 붙이세요.
- `run.sh`는 어느 폴더에서 실행해도 돼요 (`.venv`가 있으면 사용). `python run.py ...`로 실행해도 같아요.

출력 형식
```json
{
  "turn": 1,
  "input": "오빠 다음주 금요일에 시간 돼? 우리 엄마가 저녁 같이 먹재",
  "reply": "아 그거 아직 안확인했어\n확인해보고 알려줄게 ㅎㅎ",
  "reply_lines": ["아 그거 아직 안확인했어", "확인해보고 알려줄게 ㅎㅎ"],
  "emergency": {"is_emergency": false, "severity": "", "reason": ""},
  "needs_confirmation": {"is_needed": true, "question": "다음 주 금요일 저녁에 시간 되세요? ..."}
}
```
| 필드 | 설명 |
|---|---|
| `turn` | 이번 대화에서 몇 번째 메시지인지 (표준입력 모드에서 계속 증가, `/reset`하면 1부터) |
| `reply` / `reply_lines` | 내 말투로 만든 답변 (전체 / 카톡 말풍선 단위) |
| `emergency.is_emergency` | 상대가 아프거나, 다쳤거나, 위험한 상황인지 |
| `emergency.severity` | `낮음` / `중간` / `높음` |
| `needs_confirmation.is_needed` | 기억에 없어서 답할 수 없는지. 이때 `reply`는 지어내지 않고 "확인해보고 알려줄게"로 보류 |
| `needs_confirmation.question` | 나(주인)에게 물어볼 질문 |
| `error` | 실패 시에만 (예: 대화에 없는 이름). 종료 코드 1 |

### SSH 자동 터널
`.env`에 `SSH_TUNNEL`을 넣어두면 `run.sh`, `app.py`, `main.py`를 실행할 때 vLLM 서버로 가는 터널(`ssh -N -L 8000:localhost:8000 ...`)을 자동으로 열고, 끝나면 닫아요. 터미널을 따로 띄울 필요가 없어요.
```bash
# .env (GitHub에 올라가지 않음)
SSH_TUNNEL=<user>@<server>
SSH_KEY=~/.ssh/kirothon     # (선택) 키 파일. 없으면 실행할 때 SSH 비밀번호를 물어봐요
```
- `localhost:8000`이 이미 열려 있으면(터널을 직접 열어둔 경우) 그대로 써요.
- stdout(JSON)은 깨끗하게 유지되고, 터널 로그와 비밀번호 입력은 stderr와 터미널로 처리돼요.
- 서버 접속 정보는 `.env`에만 두고 저장소에는 올리지 마세요. 외부에 공유할 때는 비밀번호 대신 **포트 포워딩만 되는 전용 키**를 쓰세요 (`authorized_keys`에 `restrict,port-forwarding,permitopen="localhost:8000",command="/bin/false"` 옵션).

### 환경변수 (.env)
| 이름 | 기본값 | 설명 |
|---|---|---|
| `VLLM_BASE_URL` | `http://localhost:8000/v1` | vLLM 주소 |
| `VLLM_MODEL` | `qwen3.8-27b` | served model name |
| `MAX_MESSAGES` | `1000` | 입력: 대화 앞에서부터 사용할 메시지 수 |
| `STYLE_MESSAGES` | `500` | 그중 최근 N개로 말투 분석 |
| `MEMORY_CHUNK` | `250` | 기억 추출 구간 크기 |
| `RECENT_RAW` | `150` | 대화할 때 프롬프트에 넣을 최근 원문 메시지 수 |
| `OUTPUT_DIR` | `output` | md 저장 위치 |
| `SSH_TUNNEL` | (없음) | `user@server` 설정 시 SSH 터널 자동 연결 |
| `SSH_KEY` | (없음) | 터널용 키 파일 (없으면 비밀번호 입력) |
| `SSH_PORT` / `SSH_REMOTE_PORT` | `22` / `8000` | SSH 포트 / 서버의 vLLM 포트 |

## 설계 포인트
- **학습 없이 프롬프트만 사용**: 말투 분석, 기억 추출, 대화를 전부 Qwen3.8 하나로 처리합니다.
- **말투와 기억 분리**: 말투는 최신 습관이 중요해서 최근 500개로, 기억은 넓게 1000개 전체로 뽑습니다.
- **긴 대화 기억 보존**: 1000개를 한 번에 요약하면 사소한 약속을 놓쳐서, 250개씩 나눠 병렬로 뽑은 뒤 병합합니다. 병합할 때 바뀐 계획은 최신으로 갱신합니다.
- **md 파일 = 프롬프트**: 분석 결과를 md로 저장하고 그대로 시스템 프롬프트에 넣어, 무엇을 근거로 대답하는지 투명하고 직접 고칠 수도 있습니다.
- **판단과 답장 분리**: 같은 Qwen3.8을 '판단기' 역할로 한 번 더 호출해요. 판단기는 필요한 사실 → 기억에서 찾았는지 → 결론 순서로 JSON을 쓰게 해서 정확도를 높였어요. 비상 판단은 근거 표현을 새 메시지에서 인용하게 하고, 인용이 실제 새 메시지에 없으면 코드에서 취소해요. 그래서 이전 대화의 비상이 다음 메시지에 또 잡히지 않아요.
- **thinking 모드 제어**: Qwen3.8은 기본이 thinking 모드라서, 채팅은 꺼서 빠르게(1~2초) 하고 말투 분석만 선택적으로 켤 수 있습니다.
- **개인정보**: 대화 txt와 `output/`(분석 결과)은 `.gitignore`로 업로드에서 빠집니다.
