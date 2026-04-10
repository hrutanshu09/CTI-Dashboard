import argparse
import os
import pickle


def load_docs(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"doc mapping file not found: {path}")
    with open(path, "rb") as f:
        docs = pickle.load(f)
    if not isinstance(docs, list):
        raise TypeError("doc mapping must be a list of documents")
    return docs


def shorten(text: str, max_len: int = 220) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


def main():
    parser = argparse.ArgumentParser(description="Inspect/search rag_store/doc_mapping.pkl")
    parser.add_argument("--path", default="backend_BE/rag_store/doc_mapping.pkl", help="Path to doc_mapping.pkl")
    parser.add_argument("--search", default="", help="Case-insensitive keyword search in text/label/source")
    parser.add_argument("--limit", type=int, default=20, help="Max rows to print")
    parser.add_argument("--start", type=int, default=0, help="Start index for browsing")
    args = parser.parse_args()

    docs = load_docs(args.path)
    print(f"Loaded {len(docs)} documents from: {args.path}")

    rows = []
    keyword = args.search.strip().lower()

    if keyword:
        for idx, doc in enumerate(docs):
            text = str(doc.get("text", ""))
            label = str(doc.get("label", ""))
            source = str(doc.get("source", ""))
            blob = f"{text} {label} {source}".lower()
            if keyword in blob:
                rows.append((idx, doc))
    else:
        end = min(len(docs), args.start + max(args.limit, 1))
        for idx in range(max(args.start, 0), end):
            rows.append((idx, docs[idx]))

    if not rows:
        print("No matching documents found.")
        return

    for idx, doc in rows[: max(args.limit, 1)]:
        source = doc.get("source", "-")
        dtype = doc.get("type", "-")
        label = doc.get("label", "-")
        snippet = shorten(doc.get("text", ""))
        print(f"[{idx}] source={source} type={dtype} label={label}")
        print(f"     text: {snippet}")


if __name__ == "__main__":
    main()
