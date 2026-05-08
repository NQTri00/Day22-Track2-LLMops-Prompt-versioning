import os
import hashlib
from dotenv import load_dotenv
from config import get_config, setup_langsmith
from qa_pairs import QA_PAIRS
from langsmith import Client, traceable
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# ── 1. Environment setup ────────────────────────────────────────────────────
load_dotenv()
setup_langsmith()
config = get_config()
client = Client()

# ── 2. Define System Prompts ────────────────────────────────────────────────
PROMPT_V1_TEXT = "You are a concise assistant. Use the context to answer the question briefly.\n\nContext:\n{context}"
PROMPT_V2_TEXT = "You are a detailed research assistant. Use the provided context to give a structured, comprehensive answer. If the information is missing, explain what is missing.\n\nContext:\n{context}"

PROMPT_V1 = ChatPromptTemplate.from_messages([
    ("system", PROMPT_V1_TEXT),
    ("human", "{question}"),
])

PROMPT_V2 = ChatPromptTemplate.from_messages([
    ("system", PROMPT_V2_TEXT),
    ("human", "{question}"),
])

# ── 3. Push to Prompt Hub ───────────────────────────────────────────────────
def push_prompts():
    print("Pushing prompts to LangSmith Prompt Hub...")
    try:
        client.push_prompt("rag-prompt-v1", object=PROMPT_V1, description="Concise RAG prompt")
        client.push_prompt("rag-prompt-v2", object=PROMPT_V2, description="Detailed RAG prompt")
        print("[SUCCESS] Prompts pushed successfully.")
    except Exception as e:
        if "Conflict" in str(e) or "already exists" in str(e) or "has not changed" in str(e):
            print("[INFO] Prompts already up to date in Hub. Skipping push.")
        else:
            print(f"[ERROR] Error pushing prompts: {e}")

# ── 4. Deterministic Router ─────────────────────────────────────────────────
def get_prompt_version(request_id: str) -> str:
    """
    Deterministically routes 50/50 based on the MD5 hash of the request_id.
    """
    h = int(hashlib.md5(request_id.encode()).hexdigest(), 16)
    return "rag-prompt-v1" if h % 2 == 0 else "rag-prompt-v2"

# ── 5. Traced Query Function ────────────────────────────────────────────────
@traceable(name="ab-routing-query")
def ask_with_version(question: str, prompt_handle: str, vectorstore):
    """
    Pulls the prompt from Hub and runs the chain.
    """
    # Pull from Hub
    prompt = client.pull_prompt(prompt_handle)
    
    # Setup LLM
    llm = ChatOpenAI(
        model=config["model_name"],
        api_key=config["openai_api_key"],
        base_url=config["openai_api_base"],
    )
    
    # Setup Retriever
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)
    
    # Build Chain
    chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return chain.invoke(question)

# ── 6. Main ─────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  Step 2: Prompt Hub & A/B Routing")
    print("=" * 60)

    # Push prompts (if not already there)
    push_prompts()

    # We need the vectorstore from step 1
    # For simplicity, we rebuild it here
    from langchain_community.vectorstores import FAISS
    from langchain_openai import OpenAIEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from pathlib import Path

    embeddings = OpenAIEmbeddings(
        model=config["embedding_model"],
        api_key=config["openai_api_key"],
        base_url=config["openai_api_base"],
    )
    text = Path("data/knowledge_base.txt").read_text(encoding="utf-8")
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_text(text)
    vectorstore = FAISS.from_texts(chunks, embeddings)

    # Run A/B routing
    for i, pair in enumerate(QA_PAIRS, 1):
        question = pair["question"]
        version = get_prompt_version(question)
        answer = ask_with_version(question, version, vectorstore)
        
        print(f"[{i:02d}/{len(QA_PAIRS)}] [{version}] Q: {question[:50]}...")
        # print(f"       A: {answer[:60]}...")

    print(f"\n[SUCCESS] A/B routing complete. Check LangSmith for {len(QA_PAIRS)} additional traces.")

if __name__ == "__main__":
    main()
