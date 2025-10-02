# update_pipeline_gs_semantic_excel.py
import os, re, time, random, traceback, warnings
import pandas as pd
import tiktoken
from dotenv import load_dotenv
from tqdm import tqdm

from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Try both locations for SemanticChunker
try:
    from langchain.text_splitter import SemanticChunker   # LC >= 0.2.x
except Exception:
    try:
        from langchain_experimental.text_splitter import SemanticChunker  # Older LC
    except Exception:
        SemanticChunker = None

warnings.filterwarnings("ignore", message=".*pin_memory.*")
load_dotenv()

# =========================
# ======== Config =========
# =========================
BASE_DIR = "app/data/GS"
CHROMA_BASE_DIR = "app/embeddings_gs"
SUBFOLDERS = ["Standard_documents", "Project_documents"]

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Token/Batch controls
TOKEN_LIMIT = 280_000
MAX_TOKENS_PER_CHUNK = 8191
BATCH_SIZE = 75
SLEEP_BETWEEN_BATCHES = 1.0
MAX_RETRIES = 5
BASE_SLEEP = 5

# Logs
UNICODE_LOG_FILE = "unicode_clean_log.txt"
EXCEL_LOG_FILE = "excel_clean_log.txt"

MAX_SEMANTIC_INPUT_CHARS = 150_000  # ~50k tokens safety margin for semantic chunking

print(f"[pipeline] ✅ Using embedding model: {EMBEDDING_MODEL}")
print(f"[pipeline] ✅ OpenAI key loaded: {'YES' if OPENAI_API_KEY else 'NO'}")
if SemanticChunker is None:
    print("[pipeline] ❌ SemanticChunker not available. Excel/CSV will fail.")

# =========================
# ===== Tokenization ======
# =========================
encoding = tiktoken.encoding_for_model(EMBEDDING_MODEL)
def count_tokens(text: str) -> int:
    return len(encoding.encode(text))

# =========================
# ===== Helpers/Logs ======
# =========================
def log_to_file(file, message):
    with open(file, "a", encoding="utf-8") as f:
        f.write(message + "\n")

def safe_filter_metadata(meta: dict) -> dict:
    return {k: v for k, v in meta.items() if isinstance(v, (str, int, float, bool))}

def extract_clause_number(text: str) -> str:
    match = re.search(r'Clause\s+([\d\.]+)', text, re.IGNORECASE)
    return match.group(1) if match else "N/A"

def clean_text(text: str, source: str = "") -> str:
    cleaned = text.encode("utf-8", "ignore").decode("utf-8", "ignore")
    if cleaned != text:
        warning_msg = f"⚠️ Unicode cleaned in document from {source}"
        print(warning_msg)
        log_to_file(UNICODE_LOG_FILE, warning_msg)
    return cleaned

def with_retries(func, *args, max_retries=MAX_RETRIES, base_sleep=BASE_SLEEP, **kwargs):
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            es = str(e)
            if "429" in es or "rate limit" in es.lower() or "Connection error" in es:
                wait = base_sleep * (2 ** attempt) + random.uniform(0, 1)
                print(f"⚠️ Retry {attempt+1}/{max_retries} after {wait:.1f}s... ({es[:120]}...)")
                time.sleep(wait)
            else:
                raise
    print("❌ Max retries exceeded. Skipping operation.")
    return None

# =========================
# ====== Loaders ==========
# =========================
def load_pdf(path):
    try:
        return PyPDFLoader(path).load()
    except Exception as e:
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

def _excel_engine_for(path: str) -> str:
    lower = path.lower()
    if lower.endswith(".xlsx"): return "openpyxl"
    if lower.endswith(".xlsb"): return "pyxlsb"
    if lower.endswith(".xls"):  return "xlrd"
    return None

def preprocess_excel_to_text_blocks(path: str):
    """
    Excel/CSV → cleaned, human-readable text blocks (one per sheet).
    Logs cleaning steps; drops empty/Unnamed cols/rows.
    Returns list[(sheet_name, block_text)].
    """
    blocks = []
    try:
        if path.lower().endswith(".csv"):
            sheets = {"Sheet1": pd.read_csv(path)}
        else:
            engine = _excel_engine_for(path)
            xls = pd.ExcelFile(path, engine=engine) if engine else pd.ExcelFile(path)
            sheets = {sn: xls.parse(sn) for sn in xls.sheet_names}

        msg = f"📊 Loading tabular: {os.path.basename(path)} with {len(sheets)} sheet(s)"
        print(msg); log_to_file(EXCEL_LOG_FILE, msg)

        for sheet, df in sheets.items():
            before_rows = len(df); before_cols = len(df.columns)
            df = df.dropna(how="all").dropna(axis=1, how="all")
            if len(df.columns) > 0:
                df = df.loc[:, ~df.columns.astype(str).str.match(r"^Unnamed", na=False)]
            removed_rows = before_rows - len(df)
            removed_cols = before_cols - len(df.columns)

            if df.empty:
                msg = f"⚠️ Skipping empty sheet: '{sheet}'"
                print("   " + msg); log_to_file(EXCEL_LOG_FILE, msg)
                continue

            text = df.to_string(index=False)
            nan_ratio = text.count("NaN") / max(len(text.split()), 1)
            if nan_ratio > 0.80:
                msg = f"🚮 Skipping mostly-NaN sheet: '{sheet}' ({nan_ratio:.1%} NaN)"
                print("   " + msg); log_to_file(EXCEL_LOG_FILE, msg)
                continue

            msg = f"➡️ Sheet '{sheet}' cleaned: -{removed_rows} rows, -{removed_cols} cols | kept {len(df)} rows, {len(df.columns)} cols"
            print("   " + msg); log_to_file(EXCEL_LOG_FILE, msg)
            block = f"### Sheet: {sheet}\n{text}"
            blocks.append((sheet, block))
    except Exception as e:
        err = f"❌ Excel preprocess failed: {path} | {e}"
        print(err); log_to_file(EXCEL_LOG_FILE, err)
    return blocks

# =========================
# ====== Chunking =========
# =========================
def chunk_excel_blocks_semantic(blocks, embeddings):
    docs = []
    if not blocks: return docs
    if SemanticChunker is None:
        raise RuntimeError("SemanticChunker required but not available!")

    splitter = SemanticChunker(embeddings, breakpoint_threshold_type="percentile")
    for sheet, text in blocks:
        try:
            if len(text) > MAX_SEMANTIC_INPUT_CHARS:
                print(f"⚠️ Pre-slicing large sheet '{sheet}' ({len(text)} chars)")
                for i in range(0, len(text), MAX_SEMANTIC_INPUT_CHARS):
                    window = text[i:i+MAX_SEMANTIC_INPUT_CHARS]
                    for ch in splitter.split_text(window):
                        if ch.strip():
                            docs.append(Document(page_content=ch, metadata={"sheet": sheet, "doc_type": "excel"}))
            else:
                for ch in splitter.split_text(text):
                    if ch.strip():
                        docs.append(Document(page_content=ch, metadata={"sheet": sheet, "doc_type": "excel"}))
        except Exception as e:
            print(f"❌ Semantic chunking error in sheet '{sheet}': {e}")
    return docs

def chunk_text_documents_recursive(raw_docs):
    splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)
    chunks = splitter.split_documents(raw_docs)
    for c in chunks:
        c.metadata["doc_type"] = c.metadata.get("doc_type", "textlike")
    return chunks

# =========================
# ===== File Router =======
# =========================
def load_and_chunk_file(path: str):
    lower = path.lower()
    try:
        if lower.endswith((".xlsx", ".xlsb", ".xls", ".csv")):
            blocks = preprocess_excel_to_text_blocks(path)
            return chunk_excel_blocks_semantic(blocks, embeddings)
        elif lower.endswith(".pdf"):
            return chunk_text_documents_recursive(load_pdf(path))
        elif lower.endswith(".docx"):
            return chunk_text_documents_recursive(load_docx(path))
        elif lower.endswith(".txt"):
            return chunk_text_documents_recursive(load_txt(path))
        else:
            print(f"⚠️ Unsupported file skipped: {path}")
            return []
    except Exception as e:
        print(f"❌ Error loading/chunking {path}: {e}")
        traceback.print_exc()
        return []

# =========================
# ===== Main Pipeline =====
# =========================
embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL, openai_api_key=OPENAI_API_KEY, chunk_size=200)

def create_chroma_index():
    global_files = global_docs = global_chunks = global_embeddings = 0
    for subfolder in SUBFOLDERS:
        print(f"\n🔍 Processing GS subfolder: {subfolder}")
        folder_path = os.path.join(BASE_DIR, subfolder)
        chroma_path = os.path.join(CHROMA_BASE_DIR, subfolder)
        if not os.path.exists(folder_path):
            print(f"⚠️ Missing folder: {folder_path}")
            continue

        all_loaded_docs = []
        files = [os.path.join(root, f) for root, _, fnames in os.walk(folder_path) for f in fnames]
        for file_path in tqdm(files, desc=f"📂 Loading {subfolder}"):
            chunked_docs = load_and_chunk_file(file_path)
            for i, doc in enumerate(chunked_docs):
                doc.metadata.update({
                    "source": os.path.basename(file_path),
                    "file_path": file_path,
                    "subfolder": subfolder,
                    "project_type": "GS",
                    "project_id": os.path.splitext(os.path.basename(file_path))[0],
                    "project_title": os.path.splitext(os.path.basename(file_path))[0],
                    "page": doc.metadata.get("page", i + 1),
                    "clause": doc.metadata.get("clause", extract_clause_number(doc.page_content)),
                })
            if chunked_docs:
                all_loaded_docs.extend(chunked_docs)
                global_files += 1
                global_docs += len(chunked_docs)

        if not all_loaded_docs:
            print(f"⚠️ No documents in {subfolder}")
            continue

        print(f"📑 Loaded {len(all_loaded_docs)} chunk candidates from {subfolder}")
        chunks = all_loaded_docs
        print(f"✅ Prepared {len(chunks)} chunks")
        global_chunks += len(chunks)

        db = Chroma(persist_directory=chroma_path, embedding_function=embeddings, collection_name=subfolder)

        print("⚡ Adding embeddings into Chroma (batched)...")
        added_total = 0
        for i in tqdm(range(0, len(chunks), BATCH_SIZE), desc=f"🔗 Embedding {subfolder}"):
            batch = chunks[i:i+BATCH_SIZE]
            valid_docs = []
            for d in batch:
                text = clean_text(d.page_content, d.metadata.get("source", "unknown"))
                if 0 < count_tokens(text) <= MAX_TOKENS_PER_CHUNK:
                    valid_docs.append(Document(page_content=text, metadata=safe_filter_metadata(d.metadata)))
            if not valid_docs:
                continue
            result = with_retries(db.add_documents, valid_docs)
            if result is not None:
                added_total += len(valid_docs)
                global_embeddings += len(valid_docs)
                print(f"✅ {subfolder}: Added batch {i // BATCH_SIZE + 1} ({len(valid_docs)} docs)")
            time.sleep(SLEEP_BETWEEN_BATCHES)

        print(f"💾 Chroma DB stored at: {chroma_path} | Added: {added_total} docs")

    print("\n📊 ===== GS Semantic Excel + Recursive Text Pipeline Summary =====")
    print(f"📂 Total files processed   : {global_files}")
    print(f"📑 Total documents created : {global_docs}")
    print(f"✂️ Total chunks created    : {global_chunks}")
    print(f"🔗 Total embeddings stored : {global_embeddings}")
    print("✅ Pipeline completed successfully!")

if __name__ == "__main__":
    create_chroma_index()
