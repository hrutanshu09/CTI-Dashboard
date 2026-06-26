from typing import Optional

from RAG.retreival import retrieve_context
from core.gemini_client import generate
from RAG.rag_prompt import build_chat_rag_prompt, build_rag_prompt


def analyze_threat(
    query: str,
    report_id: Optional[str] = None,
    strict_report: bool = False,
    retrieve_mode: str = "global",
):
    # Use a deeper retrieval window to improve context recall for generation.
    retrieved_docs = retrieve_context(
        query,
        k=10,
        report_id=report_id,
        strict_report=strict_report,
        retrieve_mode=retrieve_mode,
    )

    prompt = build_rag_prompt(query, retrieved_docs)

    response = generate(prompt)

    return {
        "query": query,
        "response": response,
        "sources": retrieved_docs,
    }


def answer_followup_question(
    query: str,
    processed_context: str = "",
    report_id: Optional[str] = None,
    strict_report: bool = False,
    retrieve_mode: str = "global",
):
    retrieved_docs = retrieve_context(
        query,
        k=6,
        report_id=report_id,
        strict_report=strict_report,
        retrieve_mode=retrieve_mode,
    )

    prompt = build_chat_rag_prompt(
        query=query,
        retrieved_docs=retrieved_docs,
        processed_context=processed_context,
    )
    response = generate(prompt)

    return {
        "query": query,
        "response": response,
        "sources": retrieved_docs,
    }
