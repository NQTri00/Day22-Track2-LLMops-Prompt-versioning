import os
import json
import numpy as np
from dotenv import load_dotenv
from config import get_config, setup_langsmith
from qa_pairs import QA_PAIRS
from langsmith import Client
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pathlib import Path

# RAGAS imports
from ragas import evaluate, EvaluationDataset, SingleTurnSample
from ragas.metrics import faithfulness, answer_relevancy, context_recall, context_precision

# ── 1. Environment setup ────────────────────────────────────────────────────
load_dotenv()
setup_langsmith()
config = get_config()
client = Client()

# ── 2. Evaluation Helpers ───────────────────────────────────────────────────
def get_answers_and_contexts(prompt_handle, vectorstore):
    """
    Runs all questions through a specific prompt version and collects data for RAGAS.
    """
    print(f"Generating responses for {prompt_handle}...")
    prompt = client.pull_prompt(prompt_handle)
    llm = ChatOpenAI(
        model=config["model_name"],
        api_key=config["openai_api_key"],
        base_url=config["openai_api_base"],
        temperature=0
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    
    samples = []
    for i, pair in enumerate(QA_PAIRS, 1):
        question = pair["question"]
        reference = pair["answer"]
        
        # Retrieve docs
        docs = retriever.invoke(question)
        contexts = [doc.page_content for doc in docs]
        context_str = "\n\n".join(contexts)
        
        # Generate answer
        # prompt.invoke uses {"context": ..., "question": ...}
        chain = prompt | llm
        response = chain.invoke({"context": context_str, "question": question})
        answer = response.content
        
        sample = SingleTurnSample(
            user_input=question,
            response=answer,
            retrieved_contexts=contexts,
            reference=reference
        )
        samples.append(sample)
        if i % 10 == 0:
            print(f"  Processed {i}/{len(QA_PAIRS)} questions...")
            
    return samples

# ── 3. Main ─────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  Step 3: RAGAS Evaluation")
    print("=" * 60)

    # Initialize components
    embeddings = OpenAIEmbeddings(
        model=config["embedding_model"],
        api_key=config["openai_api_key"],
        base_url=config["openai_api_base"],
    )
    text = Path("data/knowledge_base.txt").read_text(encoding="utf-8")
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_text(text)
    vectorstore = FAISS.from_texts(chunks, embeddings)

    # LLM for RAGAS evaluation
    eval_llm = ChatOpenAI(
        model=config["model_name"],
        api_key=config["openai_api_key"],
        base_url=config["openai_api_base"],
    )

    # Evaluate V1
    samples_v1 = get_answers_and_contexts("rag-prompt-v1", vectorstore)
    dataset_v1 = EvaluationDataset(samples=samples_v1)
    print("Evaluating V1 metrics...")
    result_v1 = evaluate(
        dataset=dataset_v1,
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
        llm=eval_llm,
        embeddings=embeddings
    )

    # Evaluate V2
    samples_v2 = get_answers_and_contexts("rag-prompt-v2", vectorstore)
    dataset_v2 = EvaluationDataset(samples=samples_v2)
    print("Evaluating V2 metrics...")
    result_v2 = evaluate(
        dataset=dataset_v2,
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
        llm=eval_llm,
        embeddings=embeddings
    )

    # Process results
    metrics = ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]
    scores_v1 = {m: float(np.mean(result_v1[m])) for m in metrics}
    scores_v2 = {m: float(np.mean(result_v2[m])) for m in metrics}

    # Print Comparison Table
    print("\n" + "="*40)
    print(f"{'Metric':<20} | {'V1 (Concise)':<10} | {'V2 (Detailed)':<10}")
    print("-" * 45)
    for m in metrics:
        print(f"{m:<20} | {scores_v1[m]:.4f}     | {scores_v2[m]:.4f}")
    print("="*40)

    if scores_v1["faithfulness"] >= 0.8 or scores_v2["faithfulness"] >= 0.8:
        print("\n[SUCCESS] Target met: Faithfulness >= 0.8 for at least one version.")
    else:
        print("\n[WARNING] Target not met: Faithfulness < 0.8 for both versions.")

    # Save Report
    report = {
        "v1_scores": scores_v1,
        "v2_scores": scores_v2,
        "raw_results_v1": result_v1.to_pandas().to_dict(orient="records"),
        "raw_results_v2": result_v2.to_pandas().to_dict(orient="records")
    }
    
    report_path = Path("data/ragas_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n[SUCCESS] Report saved to {report_path}")

if __name__ == "__main__":
    main()
