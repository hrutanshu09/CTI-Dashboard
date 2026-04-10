import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- API Configuration ---
NVD_API_KEY = os.getenv("NVD_API_KEY")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

# --- FastAPI App Initialization ---
app = FastAPI()

# Configure CORS to allow your React app to make requests
origins = ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models for Request/Response ---
class AIRequest(BaseModel):
    prompt: str

class AIResponse(BaseModel):
    response: str

class CVESummaryResponse(BaseModel):
    cve_id: str
    description: str
    cvss_score: float | str
    ai_summary: str


async def generate_with_ollama(prompt: str) -> str:
    """
    Sends a prompt to local Ollama and returns the generated text.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(f"{OLLAMA_HOST}/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()


# --- API Endpoints ---

@app.get("/api/cve-summary/{cve_id}", response_model=CVESummaryResponse)
async def get_cve_summary(cve_id: str):
    """
    Fetches CVE details from the NVD API, then generates an AI summary using Gemini.
    """
    # 1. Fetch data from NVD API
    nvd_url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
    headers = {'apiKey': NVD_API_KEY} if NVD_API_KEY else {}

    async with httpx.AsyncClient() as client:
        try:
            nvd_response = await client.get(nvd_url, headers=headers)
            nvd_response.raise_for_status()
            nvd_data = nvd_response.json()

            if not nvd_data.get("vulnerabilities"):
                raise HTTPException(status_code=404, detail=f"CVE ID '{cve_id}' not found.")

            cve = nvd_data['vulnerabilities'][0]['cve']
            description = cve['descriptions'][0]['value']
            
            # Find the CVSS score
            cvss_metric = cve.get('metrics', {}).get('cvssMetricV31', [{}])[0]
            cvss_score = cvss_metric.get('cvssData', {}).get('baseScore', 'N/A')

        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail="Error fetching data from NVD.")
        except (KeyError, IndexError):
            raise HTTPException(status_code=500, detail="Could not parse CVE data.")

    # 2. Generate AI Summary with local Ollama model
    try:
        summary_prompt = (
            "You are a cybersecurity expert. Summarize the following CVE description in 2-3 sentences. "
            "Act friendly and informatively, as if explaining to a fellow security analyst. "
            "Keep the responses short and consise, focusing on the most critical information about the vulnerability. "
            "Do not explain the related the concept in detail, just provide a summary. "
            "Focus on the vulnerability type, potential impact, and key affected systems. Provide mitigation recommendations if applicable.\n\n"
            f"Description:\n\n{description}"
        )
        ai_summary = await generate_with_ollama(summary_prompt)

    except Exception as e:
        print(f"Ollama error: {e}")
        ai_summary = "Could not generate an AI summary for this CVE."

    return {
        "cve_id": cve['id'],
        "description": description,
        "cvss_score": cvss_score,
        "ai_summary": ai_summary
    }


@app.post("/api/ai-assistant", response_model=AIResponse)
async def ask_ai(request: AIRequest):
    """
    Handles general AI assistant queries using local Ollama.
    """
    try:
        cti_context = "You are an expert cybersecurity analyst for a CTI dashboard. Provide expansive, accurate threat intelligence based on the user's question."
        full_prompt = f"{cti_context}\n\nUser Question: {request.prompt}"
        
        response = await generate_with_ollama(full_prompt)
        return {"response": response}
    except Exception as e:
        print(f"Error generating content: {e}")
        raise HTTPException(status_code=500, detail="Error communicating with the local Ollama model.")
