import os, re, traceback, warnings
from dotenv import load_dotenv
from tqdm import tqdm
import pandas as pd
import tiktoken

from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from langchain_experimental.text_splitter import SemanticChunker

warnings.filterwarnings("ignore", message=".*pin_memory.*")
load_dotenv()

# 📁 Configs
BASE_DIR = "app/data/OTHER_DOCUMENTS"
CHROMA_BASE_DIR = "app/embeddings_other_documents"
VALID_SUBTYPES = ["carbon_market_general_document", "IPCC"]
TOKEN_LIMIT = 280_000
MAX_TOKENS_PER_CHUNK = 8191

# 🧠 Tokenizer
encoding = tiktoken.encoding_for_model("text-embedding-3-small")

def count_tokens(text: str) -> int:
    return len(encoding.encode(text))

def safe_filter_metadata(meta: dict) -> dict:
    return {k: v for k, v in meta.items() if isinstance(v, (str, int, float, bool))}

def extract_clause_number(text: str) -> str:
    match = re.search(r'Clause\s+([\d\.]+)', text, re.IGNORECASE)
    return match.group(1) if match else "N/A"

# ---------------------------
# Loaders
# ---------------------------

def load_pdf(path: str):
    try:
        loader = PyPDFLoader(path)
        return loader.load()
    except Exception as e:
        print(f"❌ PDF load failed: {path} | {e}")
        return []

def load_docx(path: str):
    try:
        loader = Docx2txtLoader(path)
        return loader.load()
    except Exception as e:
        print(f"❌ DOCX load failed: {path} | {e}")
        return []

def load_txt(path: str):
    try:
        loader = TextLoader(path, encoding="utf-8")
        return loader.load()
    except Exception as e:
        print(f"❌ TXT load failed: {path} | {e}")
        return []

def load_excel(path: str):
    docs = []
    try:
        engine = "openpyxl" if path.endswith(".xlsx") else "pyxlsb"
        xls = pd.ExcelFile(path, engine=engine)

        print(f"📊 Loading Excel: {os.path.basename(path)} with {len(xls.sheet_names)} sheets")

        for sheet in tqdm(xls.sheet_names, desc=f"📑 Processing sheets in {os.path.basename(path)}"):
            df = xls.parse(sheet)
            text = df.to_string(index=False)

            total_rows = len(df)
            print(f"   ➡️ Sheet '{sheet}' has {total_rows} rows")

            for i in tqdm(range(0, len(text), 2000), desc=f"   🔹 Splitting '{sheet}'"):
                chunk = text[i:i+2000]
                docs.append(Document(
                    page_content=chunk,
                    metadata={"page": 1, "clause": "N/A", "sheet": sheet}
                ))

    except Exception as e:
        print(f"❌ Excel load failed: {path} | {e}")
    return docs

def load_file(path: str):
    lower = path.lower()
    if lower.endswith(".pdf"):
        return load_pdf(path)
    if lower.endswith(".docx"):
        return load_docx(path)
    if lower.endswith(".txt"):
        return load_txt(path)
    if lower.endswith(".xlsx") or lower.endswith(".xlsb"):
        return load_excel(path)
    print(f"⚠️ Unsupported file skipped: {path}")
    return []

# ---------------------------
# Main pipeline
# ---------------------------

def create_chroma_index():
    embeddings = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"), chunk_size=100)

    splitter = SemanticChunker(
        embeddings,
        breakpoint_threshold_type="percentile",
        breakpoint_threshold_amount=95
    )

    # 🔹 Global counters
    global_files = 0
    global_docs = 0
    global_chunks = 0
    global_embeddings = 0

    for subtype in VALID_SUBTYPES:
        print(f"\n🔍 Processing subtype: {subtype}")
        folder_path = os.path.join(BASE_DIR, subtype)
        chroma_path = os.path.join(CHROMA_BASE_DIR, subtype)

        if not os.path.exists(folder_path):
            print(f"⚠️ Folder not found: {folder_path}")
            continue

        docs = []
        files = [os.path.join(root, f) for root, _, fnames in os.walk(folder_path) for f in fnames]

        for file_path in tqdm(files, desc=f"📂 Loading {subtype}"):
            try:
                loaded_docs = load_file(file_path)
                for i, doc in enumerate(loaded_docs):
                    doc.metadata.update({
                        "source": os.path.basename(file_path),
                        "file_path": file_path,
                        "subtype": subtype,
                        "project_id": os.path.splitext(os.path.basename(file_path))[0],
                        "project_title": os.path.splitext(os.path.basename(file_path))[0],
                        "page": doc.metadata.get("page", i+1),
                        "clause": doc.metadata.get("clause", extract_clause_number(doc.page_content))
                    })
                docs.extend(loaded_docs)
                if loaded_docs:
                    global_files += 1
                    global_docs += len(loaded_docs)
            except Exception as e:
                print(f"❌ Failed to process: {file_path}")
                traceback.print_exc()

        if not docs:
            print(f"⚠️ No documents found in {folder_path}")
            continue

        print(f"📑 Loaded {len(docs)} documents from {subtype}")

        print("✂️ Splitting documents into semantic chunks...")
        chunks = splitter.split_documents(docs)
        print(f"✅ Semantic split produced {len(chunks)} chunks")

        global_chunks += len(chunks)

        db = Chroma(persist_directory=chroma_path, embedding_function=embeddings, collection_name=subtype)

        print("⚡ Adding embeddings into Chroma...")
        batch, tokens, batch_id = [], 0, 1
        for doc in tqdm(chunks, desc=f"🔗 Embedding {subtype}"):
            try:
                token_len = count_tokens(doc.page_content)
                if token_len > MAX_TOKENS_PER_CHUNK or token_len == 0:
                    continue
                if tokens + token_len > TOKEN_LIMIT:
                    db.add_documents([
                        Document(page_content=d.page_content, metadata=safe_filter_metadata(d.metadata))
                        for d in batch
                    ])
                    global_embeddings += len(batch)
                    print(f"✅ {subtype}: Added batch {batch_id} ({len(batch)} docs)")
                    batch, tokens, batch_id = [], 0, batch_id + 1
                batch.append(doc)
                tokens += token_len
            except Exception as e:
                print(f"⚠️ Skipped one doc due to token error: {e}")

        if batch:
            db.add_documents([
                Document(page_content=d.page_content, metadata=safe_filter_metadata(d.metadata))
                for d in batch
            ])
            global_embeddings += len(batch)
            print(f"✅ {subtype}: Final batch {batch_id} added.")

        print(f"💾 Chroma DB stored at: {chroma_path}")

    # ---------------------------
    # Final Summary
    # ---------------------------
    print("\n📊 ===== Pipeline Summary =====")
    print(f"📂 Total files processed   : {global_files}")
    print(f"📑 Total documents created : {global_docs}")
    print(f"✂️ Total semantic chunks   : {global_chunks}")
    print(f"🔗 Total embeddings stored : {global_embeddings}")
    print("✅ Pipeline completed successfully!")

if __name__ == "__main__":
    create_chroma_index()
