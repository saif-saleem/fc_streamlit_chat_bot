import os, re, time, random, traceback, warnings, zipfile
import pandas as pd
import tiktoken
from dotenv import load_dotenv
from tqdm import tqdm
from fastkml import kml

from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker

warnings.filterwarnings("ignore", message=".*pin_memory.*")
load_dotenv()

# === Config ===
BASE_DIR = "app/data/VERRA_VCS"
CHROMA_BASE_DIR = "app/embeddings_vcs"
SUBFOLDERS = ["Standard_documents", "Project_documents"]
TOKEN_LIMIT = 280_000
MAX_TOKENS_PER_CHUNK = 8191
BATCH_SIZE = 50
SEMANTIC_BATCH_SIZE = 200
SLEEP_BETWEEN_BATCHES = 1.5
MAX_RETRIES = 5
BASE_SLEEP = 5
UNICODE_LOG_FILE = "unicode_clean_log.txt"

# === Tokenizer ===
encoding = tiktoken.encoding_for_model("text-embedding-3-small")
def count_tokens(text: str) -> int:
    return len(encoding.encode(text))

def safe_filter_metadata(meta: dict) -> dict:
    return {k: v for k, v in meta.items() if isinstance(v, (str, int, float, bool))}

def extract_clause_number(text: str) -> str:
    match = re.search(r'Clause\s+([\d\.]+)', text, re.IGNORECASE)
    return match.group(1) if match else "N/A"

# === Unicode cleaner ===
def clean_text(text: str, source: str = "") -> str:
    cleaned = text.encode("utf-8", "ignore").decode("utf-8", "ignore")
    if cleaned != text:
        warning_msg = f"⚠️ Unicode cleaned in document from {source}"
        print(warning_msg)
        with open(UNICODE_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(warning_msg + "\n")
    return cleaned

# === Retry helper ===
def with_retries(func, *args, max_retries=MAX_RETRIES, base_sleep=BASE_SLEEP, **kwargs):
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "429" in str(e) or "rate limit" in str(e).lower() or "Connection error" in str(e):
                wait = base_sleep * (2 ** attempt) + random.uniform(0, 1)
                print(f"⚠️ Retry {attempt+1}/{max_retries} after {wait:.1f}s... ({str(e)[:100]}...)")
                time.sleep(wait)
            else:
                raise
    print("❌ Max retries exceeded. Skipping operation.")
    return None

# === Loaders ===
def load_pdf(path):
    try:
        return PyPDFLoader(path).load()
    except Exception as e:
        if "cryptography" in str(e) or "AES" in str(e):
            print(f"❌ Encrypted PDF not supported: {path}")
        else:
            print(f"❌ PDF load failed: {path} | {e}")
        return []

def load_docx(path):
    try:
        return Docx2txtLoader(path).load()
    except Exception as e:
        print(f"❌ DOCX load failed: {path} | {e}")
        return []

def load_txt(path):
    try:
        return TextLoader(path, encoding="utf-8").load()
    except Exception as e:
        print(f"❌ TXT load failed: {path} | {e}")
        return []

def load_excel(path):
    docs = []
    try:
        engine = "openpyxl" if path.endswith(".xlsx") else "pyxlsb"
        xls = pd.ExcelFile(path, engine=engine)
        print(f"📊 Loading Excel: {os.path.basename(path)} with {len(xls.sheet_names)} sheets")
        for sheet in tqdm(xls.sheet_names, desc=f"📑 {os.path.basename(path)}"):
            df = xls.parse(sheet)
            text = df.to_string(index=False)
            print(f"   ➡️ Sheet '{sheet}' has {len(df)} rows")
            for i in tqdm(range(0, len(text), 2000), desc=f"   🔹 Splitting '{sheet}'"):
                chunk = text[i:i+2000]
                docs.append(Document(page_content=chunk, metadata={"page": 1, "clause": "N/A", "sheet": sheet}))
    except Exception as e:
        print(f"❌ Excel load failed: {path} | {e}")
    return docs

def load_csv(path):
    docs = []
    try:
        df = pd.read_csv(path)
        print(f"📊 Loading CSV: {os.path.basename(path)} with {len(df)} rows")
        text = df.to_string(index=False)
        for i in tqdm(range(0, len(text), 2000), desc=f"   🔹 Splitting CSV {os.path.basename(path)}"):
            chunk = text[i:i+2000]
            docs.append(Document(page_content=chunk, metadata={"page": 1, "clause": "N/A", "sheet": "CSV"}))
    except Exception as e:
        print(f"❌ CSV load failed: {path} | {e}")
    return docs

def load_kml(path):
    docs = []
    try:
        with open(path, "rt", encoding="utf-8") as f:
            content = f.read()
        k_obj = kml.KML()
        k_obj.from_string(content)
        for feature in k_obj.features():
            for placemark in feature.features():
                name, desc = getattr(placemark, "name", ""), getattr(placemark, "description", "")
                geom = placemark.geometry
                coords = str(geom) if geom else ""
                text = f"Name: {name}\nDescription: {desc}\nGeometry: {coords}"
                docs.append(Document(page_content=text, metadata={"page": 1, "clause": "N/A"}))
    except Exception as e:
        print(f"❌ KML load failed: {path} | {e}")
    return docs

def load_kmz(path):
    docs = []
    try:
        with zipfile.ZipFile(path, "r") as zf:
            for name in zf.namelist():
                if name.endswith(".kml"):
                    with zf.open(name) as kml_file:
                        content = kml_file.read().decode("utf-8", errors="ignore")
                        k_obj = kml.KML()
                        k_obj.from_string(content)
                        for feature in k_obj.features():
                            for placemark in feature.features():
                                name, desc = getattr(placemark, "name", ""), getattr(placemark, "description", "")
                                geom = placemark.geometry
                                coords = str(geom) if geom else ""
                                text = f"Name: {name}\nDescription: {desc}\nGeometry: {coords}"
                                docs.append(Document(page_content=text, metadata={"page": 1, "clause": "N/A"}))
    except Exception as e:
        print(f"❌ KMZ load failed: {path} | {e}")
    return docs

def load_file(path):
    lower = path.lower()
    if lower.endswith(".pdf"): return load_pdf(path)
    if lower.endswith(".docx"): return load_docx(path)
    if lower.endswith(".txt"): return load_txt(path)
    if lower.endswith((".xlsx", ".xlsb", ".xls")): return load_excel(path)
    if lower.endswith(".csv"): return load_csv(path)
    if lower.endswith(".kml"): return load_kml(path)
    if lower.endswith(".kmz"): return load_kmz(path)
    print(f"⚠️ Unsupported file skipped: {path}")
    return []

# === Semantic batching ===
def semantic_split_in_batches(docs, splitter, batch_size=SEMANTIC_BATCH_SIZE):
    all_chunks = []
    for i in range(0, len(docs), batch_size):
        batch = docs[i:i+batch_size]
        print(f"✂️ Semantic splitting batch {i//batch_size+1}/{(len(docs)+batch_size-1)//batch_size} ({len(batch)} docs)...")
        chunks = with_retries(splitter.split_documents, batch)
        if chunks:
            all_chunks.extend(chunks)
            print(f"   ✅ Produced {len(chunks)} chunks in this batch")
        time.sleep(1)
    return all_chunks

# === Main Pipeline ===
def create_chroma_index():
    embeddings = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"), chunk_size=100)
    recursive_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    semantic_splitter = SemanticChunker(embeddings, breakpoint_threshold_type="percentile", breakpoint_threshold_amount=95)

    global_files, global_docs, global_chunks, global_embeddings = 0, 0, 0, 0

    for subfolder in SUBFOLDERS:
        print(f"\n🔍 Processing VCS subfolder: {subfolder}")
        folder_path = os.path.join(BASE_DIR, subfolder)
        chroma_path = os.path.join(CHROMA_BASE_DIR, subfolder)

        if not os.path.exists(folder_path):
            print(f"⚠️ Missing folder: {folder_path}")
            continue

        docs = []
        files = [os.path.join(root, f) for root, _, fnames in os.walk(folder_path) for f in fnames]

        for file_path in tqdm(files, desc=f"📂 Loading {subfolder}"):
            try:
                loaded_docs = load_file(file_path)
                for i, doc in enumerate(loaded_docs):
                    doc.metadata.update({
                        "source": os.path.basename(file_path),
                        "file_path": file_path,
                        "subfolder": subfolder,
                        "project_type": "VCS",
                        "project_id": re.search(r'(VCS\d+)', os.path.basename(file_path), re.I).group(1)
                                      if re.search(r'(VCS\d+)', os.path.basename(file_path), re.I) else "VCS",
                        "project_title": os.path.splitext(os.path.basename(file_path))[0],
                        "page": doc.metadata.get("page", i+1),
                        "clause": doc.metadata.get("clause", extract_clause_number(doc.page_content))
                    })
                docs.extend(loaded_docs)
                if loaded_docs:
                    global_files += 1
                    global_docs += len(loaded_docs)
            except Exception:
                print(f"❌ Failed: {file_path}")
                traceback.print_exc()

        if not docs:
            print(f"⚠️ No documents in {folder_path}")
            continue

        print(f"📑 Loaded {len(docs)} documents from {subfolder}")

        if subfolder == "Project_documents":
            chunks = semantic_split_in_batches(docs, semantic_splitter)
        else:
            chunks = recursive_splitter.split_documents(docs)

        print(f"✅ Produced {len(chunks)} chunks")
        global_chunks += len(chunks)

        db = Chroma(persist_directory=chroma_path, embedding_function=embeddings, collection_name=subfolder)

        print("⚡ Adding embeddings into Chroma (batched)...")
        for i in tqdm(range(0, len(chunks), BATCH_SIZE), desc=f"🔗 Embedding {subfolder}"):
            batch = chunks[i:i+BATCH_SIZE]
            valid_docs = [
                Document(
                    page_content=clean_text(d.page_content, d.metadata.get("source", "unknown")),
                    metadata=safe_filter_metadata(d.metadata)
                )
                for d in batch if 0 < count_tokens(d.page_content) <= MAX_TOKENS_PER_CHUNK
            ]
            if not valid_docs:
                continue
            result = with_retries(db.add_documents, valid_docs)
            if result is not None:
                global_embeddings += len(valid_docs)
                print(f"✅ {subfolder}: Added batch {i//BATCH_SIZE + 1} ({len(valid_docs)} docs)")
            time.sleep(SLEEP_BETWEEN_BATCHES)

        print(f"💾 Chroma DB stored at: {chroma_path}")

    print("\n📊 ===== Pipeline Summary =====")
    print(f"📂 Total files processed   : {global_files}")
    print(f"📑 Total documents created : {global_docs}")
    print(f"✂️ Total chunks created    : {global_chunks}")
    print(f"🔗 Total embeddings stored : {global_embeddings}")
    print("✅ Pipeline completed successfully!")

if __name__ == "__main__":
    create_chroma_index()
