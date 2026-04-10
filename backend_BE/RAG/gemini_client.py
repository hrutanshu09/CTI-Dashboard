import os
import google.generativeai as genai

# Load environment variables from .env.txt if they're not already set
if not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    env_path = os.path.join(os.getcwd(), "CTI-Dashboard-backend-integration", ".env.txt")
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and v and not os.getenv(k):
                        os.environ[k] = v
    except FileNotFoundError:
        pass

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# Try available models
DEFAULT_MODEL_PREFERENCES = [
    "models/gemini-2.5-flash",
    "models/gemini-1.5-pro",
    "models/gemini-1.5-flash",
]

model = None
for model_name in DEFAULT_MODEL_PREFERENCES:
    try:
        model = genai.GenerativeModel(model_name)
        break
    except Exception:
        continue

def generate(prompt):
    """
    Generate response using Gemini API.
    
    Args:
        prompt: The prompt text
    
    Returns:
        Generated text response
    """
    if not model:
        return "Error: Could not initialize any Gemini model"
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating response: {str(e)}"