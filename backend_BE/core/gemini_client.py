import httpx
import google.generativeai as genai
from openai import OpenAI
from core.config import settings


def _generate_with_ollama(prompt: str) -> str:
    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    try:
        response = httpx.post(
            f"{settings.OLLAMA_HOST.rstrip('/')}/api/generate",
            json=payload,
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()
        return str(data.get("response", "")).strip()
    except Exception as e:
        raise RuntimeError(f"Ollama generation failed: {str(e)}")


def _generate_with_groq(prompt: str) -> str:
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")

    try:
        client = OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return str(response.choices[0].message.content or "").strip()
    except Exception as e:
        raise RuntimeError(f"Groq generation failed: {str(e)}")


def _initialize_gemini_model():
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    genai.configure(api_key=settings.GEMINI_API_KEY)

    for model_name in settings.MODEL_PREFERENCES:
        try:
            return genai.GenerativeModel(model_name)
        except Exception:
            continue

    raise RuntimeError("No Gemini model could be initialized")


_gemini_model = None


def _generate_with_gemini(prompt: str) -> str:
    global _gemini_model
    if _gemini_model is None:
        _gemini_model = _initialize_gemini_model()
    try:
        response = _gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        raise RuntimeError(f"Gemini generation failed: {str(e)}")


def generate(prompt: str) -> str:
    provider = (settings.LLM_PROVIDER or "groq").strip().lower()
    if provider == "groq":
        return _generate_with_groq(prompt)
    if provider == "ollama":
        return _generate_with_ollama(prompt)
    return _generate_with_gemini(prompt)
