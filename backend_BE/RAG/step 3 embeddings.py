from sentence_transformers import SentenceTransformer
import numpy as np
import pickle

def generate_embeddings(chunked_docs):
    model = SentenceTransformer("all-MiniLM-L6-v2")

    texts = [doc["text"] for doc in chunked_docs]

    embeddings = model.encode(
        texts,
        show_progress_bar=True,
        normalize_embeddings=True
    )

    embeddings = np.array(embeddings)

    # Persist everything (CRITICAL)
    with open("embeddings.pkl", "wb") as f:
        pickle.dump({
            "embeddings": embeddings,
            "documents": chunked_docs
        }, f)

    return embeddings

# Load chunked documents produced by the previous step
with open("rag_store/chunked_docs.pkl", "rb") as f:
    chunked_docs = pickle.load(f)

embeddings = generate_embeddings(chunked_docs)
print(embeddings.shape)

assert embeddings.shape[1] == 384
