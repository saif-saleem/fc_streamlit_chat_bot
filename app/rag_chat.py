import os
from dotenv import load_dotenv
from openai import OpenAI
from app.utils import (
    retrieve_context,
    expand_query_variants
)

load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

chat_state = {}

def _normalize_standard_key(s):
    if not s:
        return None
    s_low = s.lower().replace("-", "_").replace(" ", "_")
    mapping = {
        "vcs": "vcs", "verra": "vcs",
        "icr": "icr",
        "plan_vivo": "plan_vivo", "planvivo": "plan_vivo",
        "other": "other",
        "gs": "gs", "gold_standard": "gs"   # ✅ NEWLY ADDED
    }
    return mapping.get(s_low, None)


def batch_chunks(lst, n):
    """Yield successive n-sized batches from list."""
    for i in range(0, len(lst), n):
        yield lst[i:i+n]


def get_answer(query=None, selected_standard=None, follow_up_answer=None,
               original_query=None, model="gpt-4.1", temperature=0.0):

    if not selected_standard:
        return {"clarification": "Please choose a standard: VCS, ICR, PLAN_VIVO, GS, OTHER",
                "answer": None, "sources": [], "highlights": []}

    standard_key = _normalize_standard_key(selected_standard)
    if not standard_key:
        return {"answer": "Invalid or unsupported standard selected.", "sources": [], "highlights": []}

    chat_state["standard_used"] = standard_key
    chat_state["original_query"] = query or original_query

    # Step 1: Retrieve docs
    results = retrieve_context(query, selected_standard=standard_key, top_k=20, return_scores=True)
    if not results:
        return {"answer": "No relevant information found.", "sources": [], "highlights": []}

    sources = [doc.metadata for doc, _ in results]

    # --- MAP Phase with batching ---
    summaries = []
    batch_size = 5
    for batch in batch_chunks(results, batch_size):
        batch_text = ""
        for i, (doc, _) in enumerate(batch, start=1):
            batch_text += f"\nCHUNK {i}:\n{doc.page_content}\n"

        map_prompt = f"""
        QUESTION: {query}

        You are given multiple CHUNKS of text. For EACH CHUNK:

        1. Summarize only the information relevant to the QUESTION.
        2. Write the summary in bullet points.
        3. If the CHUNK contains reference info (page numbers, section titles, or document names), include it in parentheses.

        {batch_text}
        """
        try:
            resp = openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a summarization assistant."},
                    {"role": "user", "content": map_prompt}
                ],
                temperature=0
            )
            summaries.append(resp.choices[0].message.content.strip())
        except Exception as e:
            summaries.append(f"[Error summarizing batch: {e}]")

    # --- REDUCE Phase ---
    reduce_prompt = f"""
    QUESTION: {query}

    You are given multiple PARTIAL SUMMARIES extracted from different chunks of documents.

    TASK:
    - Write a comprehensive, exhaustive, and well-structured answer to the QUESTION.
    - Present the answer in a numbered or bulleted format.
    - Merge overlapping points but do not drop unique details.
    - Always cite references in parentheses if present (e.g., Page 12, Section 4.2, Project Document).
    - Organize the answer by themes or categories if multiple aspects are present.

    PARTIAL SUMMARIES:
    {chr(10).join(summaries)}
    """
    final_resp = openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an expert assistant specialized in carbon credit standards."},
            {"role": "user", "content": reduce_prompt}
        ],
        temperature=temperature
    )

    final_answer = final_resp.choices[0].message.content.strip()

    highlights = [{"snippet": doc.page_content[:200] + "...", "page": doc.metadata.get("page", "N/A")}
                  for doc, _ in results]

    return {"answer": final_answer, "sources": sources, "highlights": highlights}
