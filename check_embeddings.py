import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma

load_dotenv()

# === Config ===
CHROMA_DIR = "app/embeddings_vcs"
COLLECTIONS = ["Standard_documents", "Project_documents"]

QUERY = "What is the VCS Standard?"
TOP_K = 5

# === Init ===
embeddings = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=os.getenv("OPENAI_API_KEY"))

def test_collection(collection_name, query):
    print(f"\n📂 Checking collection: {collection_name}")

    db = Chroma(
        persist_directory=os.path.join(CHROMA_DIR, collection_name),
        embedding_function=embeddings,
        collection_name=collection_name
    )

    results = db.similarity_search(query, k=TOP_K)
    print(f"   📊 Retrieved {len(results)} docs for query: {query}\n")

    # Show retrieved docs
    for idx, doc in enumerate(results, 1):
        snippet = doc.page_content[:500].replace("\n", " ")
        print(f"--- Result {idx} ---")
        print(snippet)
        print(f"Source: {doc.metadata.get('source')} | Page: {doc.metadata.get('page')}")
        print()

    # Build context with explicit source references
    context = "\n\n".join(
        f"From {doc.metadata.get('source')} (page {doc.metadata.get('page')}):\n{doc.page_content[:1000]}"
        for doc in results
    )

    # Ask LLM to answer WITH sources
    prompt = f"""You are a helpful assistant.
The user asked: {query}

Use ONLY the provided documents to answer.
For every part of your answer, include the filename and page number from which it came.
If you cannot find an answer in the documents, say "Not found in documents".

Context:
{context}

Final Answer with sources:"""

    answer = llm.invoke(prompt).content
    print(f"💡 LLM Answer:\n{answer}\n")

if __name__ == "__main__":
    for col in COLLECTIONS:
        test_collection(col, QUERY)
