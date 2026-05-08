import os
from pathlib import Path
from dotenv import load_dotenv
from config import get_config, setup_langsmith
from qa_pairs import QA_PAIRS

# ── 1. Environment setup ────────────────────────────────────────────────────
load_dotenv()
setup_langsmith()
config = get_config()

# ── 2. LangChain + LangSmith imports ────────────────────────────────────────
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langsmith import traceable

# ── 3. LLM and Embeddings ───────────────────────────────────────────────────
llm = ChatOpenAI(
    model=config["model_name"],
    api_key=config["openai_api_key"],
    base_url=config["openai_api_base"],
)

embeddings = OpenAIEmbeddings(
    model=config["embedding_model"],
    api_key=config["openai_api_key"],
    base_url=config["openai_api_base"],
)

# ── 4. Build FAISS vector store ─────────────────────────────────────────────
def build_vectorstore():
    """
    Load the knowledge base, split into chunks, embed and index with FAISS.
    """
    kb_path = Path("data/knowledge_base.txt")
    if not kb_path.exists():
        raise FileNotFoundError(f"Knowledge base not found at {kb_path}")
    
    text = kb_path.read_text(encoding="utf-8")

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_text(text)
    print(f"Split into {len(chunks)} chunks")

    vectorstore = FAISS.from_texts(chunks, embeddings)
    return vectorstore

# ── 5. RAG prompt template ──────────────────────────────────────────────────
RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. Use the context below to answer the question. If you don't know the answer based on the context, just say that you don't know, don't try to make up an answer.\n\nContext:\n{context}"),
    ("human",  "{question}"),
])

# ── 6. Build the RAG chain ──────────────────────────────────────────────────
def build_rag_chain(vectorstore):
    """
    Build a LangChain RAG chain using LCEL.
    """
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | RAG_PROMPT
        | llm
        | StrOutputParser()
    )
    return chain, retriever

# ── 7. Traced query function ────────────────────────────────────────────────
@traceable(name="rag-query", tags=["rag", "step1"])
def ask(chain, question: str) -> str:
    """
    Run the RAG chain on a single question.
    """
    return chain.invoke(question)

# ── 8. Main ─────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  Step 1: LangSmith RAG Pipeline")
    print("=" * 60)

    # Build the vectorstore
    vectorstore = build_vectorstore()

    # Build the RAG chain
    chain, _ = build_rag_chain(vectorstore)

    # Loop through all QA_PAIRS
    for i, pair in enumerate(QA_PAIRS, 1):
        question = pair["question"]
        answer = ask(chain, question)
        print(f"[{i:02d}/{len(QA_PAIRS)}] Q: {question[:60]}...")
        print(f"       A: {answer[:100]}...\n")

    print(f"[SUCCESS] {len(QA_PAIRS)} traces sent to LangSmith project '{os.environ['LANGCHAIN_PROJECT']}'")
    print("   Open https://smith.langchain.com to view traces.")

if __name__ == "__main__":
    main()
