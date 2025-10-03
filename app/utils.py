import os
import re
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.prompts import PromptTemplate

load_dotenv()

# === Config ===
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

print(f"[utils] ✅ Using embedding model: {EMBEDDING_MODEL}")
print(f"[utils] ✅ OpenAI key loaded: {'YES' if OPENAI_API_KEY else 'NO'}")

# === Active Chroma specs ===
CHROMA_SPECS = {
    "vcs": [
        {"path": "app/embeddings_vcs/Project_documents", "collection": "Project_documents"},
        {"path": "app/embeddings_vcs/Standard_documents", "collection": "Standard_documents"},
    ],
    "icr": [
        {"path": "app/embeddings_icr/Project_documents", "collection": "Project_documents"},
        {"path": "app/embeddings_icr/Standard_documents", "collection": "Standard_documents"},
    ],
    "plan_vivo": [
        {"path": "app/embeddings_plan_vivo/Project_documents", "collection": "Project_documents"},
        {"path": "app/embeddings_plan_vivo/Standard_documents", "collection": "Standard_documents"},
    ],
    "other": [
        {"path": "app/embeddings_other_documents/carbon_market_general_document", "collection": "carbon_market_general_document"},
        {"path": "app/embeddings_other_documents/IPCC", "collection": "IPCC"},
    ],
    "gs": [   # ✅ NEWLY ADDED
        {"path": "app/embeddings_gs/Project_documents", "collection": "Project_documents"},
        {"path": "app/embeddings_gs/Standard_documents", "collection": "Standard_documents"},
    ],
}

# === Cache ===
_CHROMA_CACHE = {}
_EMBEDDING_MODEL_SINGLETON = None


def _get_embedding_model():
    global _EMBEDDING_MODEL_SINGLETON
    if _EMBEDDING_MODEL_SINGLETON is None:
        print(f"[utils] Initializing embedding model: {EMBEDDING_MODEL}")
        _EMBEDDING_MODEL_SINGLETON = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            openai_api_key=OPENAI_API_KEY,
        )
    return _EMBEDDING_MODEL_SINGLETON


def _load_chroma_db(persist_path: str, collection_name: str | None):
    cache_key = f"{persist_path}:::{collection_name or 'DEFAULT'}"
    if cache_key in _CHROMA_CACHE:
        return _CHROMA_CACHE[cache_key]

    if not os.path.exists(persist_path):
        print(f"[utils] ❌ Missing path: {persist_path}")
        return None

    try:
        db = Chroma(
            persist_directory=persist_path,
            collection_name=collection_name,
            embedding_function=_get_embedding_model(),
        ) if collection_name else Chroma(
            persist_directory=persist_path,
            embedding_function=_get_embedding_model(),
        )

        count = len(db.get()["ids"])
        print(f"[utils] ✅ Loaded Chroma at {persist_path} | Docs: {count}")

        _CHROMA_CACHE[cache_key] = db
        return db
    except Exception as e:
        print(f"[utils] ❌ Error opening Chroma at {persist_path}: {e}")
        return None


def _similarity_search_from_db(db, query, k=10):
    if not db:
        return []
    try:
        results = db.similarity_search_with_relevance_scores(query, k=k)
        print(f"[utils] 🔎 Query='{query[:50]}...' | Retrieved {len(results)} results")
        return results
    except Exception as e:
        print(f"[utils] ❌ Error during similarity search: {e}")
        return []


def expand_query_variants(query):
    words = re.findall(r"[A-Za-z0-9\-]+", query.lower())
    stop = {"what","how","the","in","is","a","an","and","or","to","for","of","on","by","be","are","was","were","it","this","that","with","as","at","from"}
    kws = [w.rstrip("s") for w in words if len(w) >= 3 and w not in stop]
    variants = [query]
    if kws:
        variants.append(" ".join(kws))
    if len(kws) > 3:
        variants.append(" ".join(kws[:3]))
    return list(dict.fromkeys(variants))


def retrieve_context(query, selected_standard=None, top_k=20, return_scores=False):
    if not query:
        return []

    variants = expand_query_variants(query)
    print(f"[utils] 🔎 Query variants: {variants}")

    search_keys = [selected_standard] if selected_standard else list(CHROMA_SPECS.keys())

    aggregated = []
    for sk in search_keys:
        for spec in CHROMA_SPECS.get(sk, []):
            db = _load_chroma_db(spec["path"], spec.get("collection"))
            if not db:
                continue
            for vq in variants:
                aggregated.extend(_similarity_search_from_db(db, vq, k=top_k))

    if not aggregated:
        print(f"[utils] ❌ No results for query: {query}")
        return []

    aggregated = sorted(aggregated, key=lambda x: x[1], reverse=True)[:top_k]
    if return_scores:
        return aggregated

    context = "\n\n".join([doc.page_content for doc, _ in aggregated])
    sources = [doc.metadata for doc, _ in aggregated]
    return context, sources, sources, sources