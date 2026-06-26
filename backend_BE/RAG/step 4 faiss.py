import faiss
import numpy as np
import pickle
import os

# Use script directory for rag_store directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STORE_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "rag_store")
EMBED_PKL_PATH = os.path.join(STORE_DIR, "embeddings.pkl")
EMBED_PATH = os.path.join(STORE_DIR, "embeddings.npy")
CHUNKS_PATH = os.path.join(STORE_DIR, "chunked_docs.pkl")
INDEX_PATH = os.path.join(STORE_DIR, "faiss.index")
META_PATH = os.path.join(STORE_DIR, "doc_mapping.pkl")

if os.path.exists(EMBED_PATH):
    embeddings = np.load(EMBED_PATH).astype("float32")
else:
    with open(EMBED_PKL_PATH, "rb") as f:
        data = pickle.load(f)

    # Some previous steps persisted a dict like {"embeddings": array, "documents": [...]}
    if isinstance(data, dict):
        embeddings = data.get("embeddings", data)
    else:
        embeddings = data

    embeddings = np.array(embeddings, dtype="float32")
    np.save(EMBED_PATH, embeddings)
    print("Saved embeddings.npy with shape:", embeddings.shape)

# Load chunk metadata
with open(CHUNKS_PATH, "rb") as f:
    chunked_docs = pickle.load(f)

print("Embeddings shape:", embeddings.shape)
print("Chunked docs:", len(chunked_docs))

if embeddings.shape[0] != len(chunked_docs):
    raise RuntimeError(
        f"Embeddings/documents mismatch: embeddings={embeddings.shape[0]}, docs={len(chunked_docs)}. "
        "Regenerate embeddings before rebuilding FAISS."
    )

# Build FAISS index
dimension = embeddings.shape[1]
index = faiss.IndexFlatL2(dimension)
index.add(embeddings)

# Save index
faiss.write_index(index, INDEX_PATH)

# Save mapping (chunk_id -> document)
with open(META_PATH, "wb") as f:
    pickle.dump(chunked_docs, f)

print("FAISS index saved successfully")
