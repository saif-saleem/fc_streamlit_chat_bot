# check_embeddings.py
import os
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from openai import OpenAI  # ✅ new SDK

load_dotenv()

# === Config ===
EMBEDDINGS_DIR = "app/embeddings_gs"
SUBFOLDERS = ["Standard_documents", "Project_documents"]
OPENAI_MODEL = "gpt-4.1"  # or "gpt-4.1"
TOP_K = 8  # number of docs per collection

# Initialize embeddings + client
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_key=os.getenv("OPENAI_API_KEY"),
)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def test_query(query="What project in gold standard planted Tectona grandis and what allotmetric equation they used?"):
    retrieved_chunks = []

    for subfolder in SUBFOLDERS:
        print(f"\n📂 Checking GS collection: {subfolder}")
        persist_path = os.path.join(EMBEDDINGS_DIR, subfolder)

        if not os.path.exists(persist_path):
            print(f"❌ Path not found: {persist_path}")
            continue

        try:
            db = Chroma(
                persist_directory=persist_path,
                embedding_function=embeddings,
                collection_name=subfolder,
            )

            results = db.similarity_search_with_relevance_scores(query, k=TOP_K)
            if not results:
                print("⚠️ No results found.")
                continue

            # Normalize and sort results
            normalized_results = []
            for doc, score in results:
                norm_score = (score + 1) / 2  # convert [-1,1] → [0,1]
                normalized_results.append((doc, score, norm_score))

            normalized_results.sort(key=lambda x: x[2], reverse=True)

            for i, (doc, raw, norm) in enumerate(normalized_results, start=1):
                print(f"\n--- Result {i} ---")
                print(doc.page_content[:500])  # Preview first 500 chars
                print(f"Metadata: {doc.metadata}")
                print(f"Raw Score: {raw}")
                print(f"Normalized Score: {norm:.4f}")

                retrieved_chunks.append(doc.page_content)

        except Exception as e:
            print(f"❌ Error checking {subfolder}: {e}")

    # === Final summarization with OpenAI ===
    if not retrieved_chunks:
        print("\n⚠️ No context retrieved, cannot generate answer.")
        return

    combined_context = "\n\n".join(retrieved_chunks[:15])  # take top 15 chunks max

    prompt = f"""
You are an expert on carbon credit standards.
Answer the following query comprehensively using ONLY the context provided.

Query:
{query}

Context:
{combined_context}

Now provide a clear, well-structured answer with references.
"""

    print("\n⏳ Generating final answer from retrieved chunks...")
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert on carbon credit standards."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        final_answer = resp.choices[0].message.content.strip()

        print("\n✅ ===== FINAL ANSWER =====\n")
        print(final_answer)

    except Exception as e:
        print(f"❌ Error generating final answer: {e}")


if __name__ == "__main__":
    test_query("What project in gold standard planted Tectona grandis and what allotmetric equation they used??")
