import textwrap


def build_rag_prompt(query, retrieved_docs):
    context = "\n\n".join(
        f"[Source {i+1}] {doc['text']}"
        for i, doc in enumerate(retrieved_docs)
    )

    prompt = f"""
You are a senior Cyber Threat Intelligence analyst.

You MUST use only the provided CONTEXT.
Do not invent facts. If context is missing, say "Insufficient context".

CONTEXT:
{context}

USER QUERY:
{query}

Return your answer in exactly this structure:

1) Threat/Behavior
- 1-2 bullets explaining likely threat behavior or attack type.

2) Key Indicators
- 2-4 bullets with observable indicators (IPs, repeated patterns, protocol/log signals, suspicious paths, failed-auth patterns).

3) Detection Signals
- 2-4 bullets with concrete SOC monitoring signals.

4) Mitigations
- 3-5 concise, actionable mitigations.

Rules:
- Keep bullets concrete and operational.
- Prefer wording tied to log evidence and detection activity.
- Avoid generic cybersecurity advice not grounded in context.
"""

    return textwrap.dedent(prompt)


def build_chat_rag_prompt(query, retrieved_docs, processed_context=""):
    retrieved_context = "\n\n".join(
        f"[Retrieved {i+1}] {doc.get('text', '')}"
        for i, doc in enumerate(retrieved_docs)
        if isinstance(doc, dict)
    )

    prompt = f"""
You are a concise SOC chatbot for a CTI dashboard.

Answer the user's question using the uploaded/processed report context first.
Use retrieved context only when it helps.
Do not force a fixed report structure.
Do not invent facts. If the available context is insufficient, say so briefly.

Keep the answer short:
- Prefer 2-5 sentences, or up to 5 bullets if a list is clearer.
- Be direct and operational.
- Avoid long explanations and generic cybersecurity advice.

PROCESSED UPLOAD CONTEXT:
{processed_context}

RETRIEVED CONTEXT:
{retrieved_context}

USER QUESTION:
{query}
"""

    return textwrap.dedent(prompt)
