from services.rag_services import analyze_threat

query = "Multiple failed login attempts from suspicious IP"

print(analyze_threat(query))
