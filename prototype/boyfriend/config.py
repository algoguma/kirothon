"""환경설정. 모든 LLM 호출은 원격 vLLM(OpenAI 호환 API)의 Qwen3.8로만 갑니다."""
import os


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 프로젝트 폴더


def _load_dotenv(path: str = os.path.join(ROOT, ".env")) -> None:
    """의존성 없이 .env 읽기 (이미 설정된 환경변수가 우선)"""
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "EMPTY")
VLLM_MODEL = os.getenv("VLLM_MODEL", "qwen3.8-27b")

# 대화 파일에서 앞에서부터 몇 개 메시지를 입력으로 쓸지
MAX_MESSAGES = int(os.getenv("MAX_MESSAGES", "1000"))
# 그중 최근 몇 개로 말투를 분석할지
STYLE_MESSAGES = int(os.getenv("STYLE_MESSAGES", "500"))
# 기억 추출 시 한 번에 Qwen에 넣는 메시지 수 (구간별로 나눠 디테일 보존)
MEMORY_CHUNK = int(os.getenv("MEMORY_CHUNK", "250"))
# 대화할 때 프롬프트에 원문 그대로 넣을 최근 메시지 수 (말투/직전 맥락용)
RECENT_RAW = int(os.getenv("RECENT_RAW", "150"))
# 분석 결과(style.md, memory.md) 저장 폴더
OUTPUT_DIR = os.path.join(ROOT, os.getenv("OUTPUT_DIR", "output"))  # 상대경로면 프로젝트 기준
