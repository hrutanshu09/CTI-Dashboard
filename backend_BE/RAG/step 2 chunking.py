from langchain_text_splitters import RecursiveCharacterTextSplitter

import pickle
# LOAD
with open("rag_store/documents.pkl", "rb") as f:
    documents = pickle.load(f)


def chunk_documents(documents):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=80
    )

    chunked_docs = []

    for doc in documents:
        # Only chunk attack knowledge
        if doc["type"] == "attack_knowledge":
            chunks = splitter.split_text(doc["text"])

            for i, chunk in enumerate(chunks):
                chunked_docs.append({
                    "text": chunk,
                    "source": doc["source"],
                    "type": doc["type"],
                    "label": doc["label"],
                    "metadata": {
                        **doc["metadata"],
                        "chunk_id": i
                    }
                })
        else:
            # Keep others as-is
            chunked_docs.append(doc)

    return chunked_docs

with open("rag_store/chunked_docs.pkl", "wb") as f:
    # Generate chunked documents from the loaded documents
    chunked_docs = chunk_documents(documents)

    pickle.dump(chunked_docs, f)

print("Saved", len(chunked_docs), "chunked documents")