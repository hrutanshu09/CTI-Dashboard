import google.generativeai as genai
from core.config import settings


# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)


def _initialize_model():

    for model_name in settings.MODEL_PREFERENCES:
        try:
            return genai.GenerativeModel(model_name)
        except Exception:
            continue

    raise RuntimeError("No Gemini model could be initialized")


model = _initialize_model()


def generate(prompt: str) -> str:
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        raise RuntimeError(f"Gemini generation failed: {str(e)}")
