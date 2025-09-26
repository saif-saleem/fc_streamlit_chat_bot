import os
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

persist_path = "app/embeddings_icr/Standard_documents"

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

# Try both collections
for cname in ["Standard_documents", "langchain"]:
    db = Chroma(persist_directory=persist_path, embedding_function=embeddings, collection_name=cname)
    count = db._collection.count()
    print(f"📊 Collection '{cname}' → {count} embeddings")

    if count > 0:
        results = db.similarity_search("ICR", k=3)
        for r in results:
            print("---")
            print("Content:", r.page_content[:200])
            print("Metadata:", r.metadata)
