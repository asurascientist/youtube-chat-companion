from transcription import initialize_and_load_index
import json
from time import time

from openai import OpenAI

client = OpenAI()
index = initialize_and_load_index()

def search(query, video_id):
    boost = {}

    results = index.search(
        query=query,
        filter_dict = {"video_id":video_id},
        boost_dict=boost,
        num_results=5
    )
    return results

prompt_template = """
You're a video assistant. Answer the QUESTION based on the CONTEXT from our YouTube transcript chunks.
- If the QUESTION and CONTEXT are in different languages, translate the CONTEXT to match the QUESTION language before answering.
- Use only the information from the CONTEXT when answering the QUESTION.

QUESTION: {question}

CONTEXT:
{context}
""".strip()

entry_template = """
subtitle: {subtitle}
text_chunk: {text_chunk}
""".strip()

def build_prompt(query, transcript_chunks):
    context = ""
    
    for chunk in transcript_chunks:
        context += entry_template.format(**chunk) + "\n\n"

    prompt = prompt_template.format(question=query, context=context).strip()
    return prompt

def llm(prompt, model='gpt-4o-mini'):
    response = client.chat.completions.create(
        model = model,
        messages=[{"role":"user", "content": prompt}]
    )
    answer = response.choices[0].message.content
    token_stats = {
        'prompt_tokens':response.usage.prompt_tokens,
        'completion_tokens':response.usage.completion_tokens,
        'total_tokens':response.usage.total_tokens
    }
    return answer, token_stats

evaluation_prompt_template = """
You are an expert evaluator for a RAG system.
Your task is to analyze the relevance of the generated answer to the given question.
Based on the relevance of the generated answer, you will classify it
as "NON_RELEVANT", "PARTLY_RELEVANT", or "RELEVANT".

Here is the data for evaluation:

Question: {question}
Generated Answer: {answer}

Please analyze the content and context of the generated answer in relation to the question
and provide your evaluation in parsable JSON without using code blocks:

{{
  "Relevance": "NON_RELEVANT" | "PARTLY_RELEVANT" | "RELEVANT",
  "Explanation": "[Provide a brief explanation for your evaluation]"
}}
""".strip()

def evaluate_relevance(question, answer):
    prompt = evaluation_prompt_template.format(question=question, answer=answer)
    evaluation, tokens = llm(prompt, model="gpt-4o-mini")

    try:
        json_eval = json.loads(evaluation)
        return json_eval, tokens
    except json.JSONDecodeError:
        result = {"Relevance": "UNKNOWN", "Explanation": "Failed to parse evaluation"}
        return result, tokens

def calculate_openai_cost(model, tokens):
    openai_cost = 0

    if model == "gpt-4o-mini":
        openai_cost = (
            tokens["prompt_tokens"] * 0.00015 + tokens["completion_tokens"] * 0.0006
        ) / 1000
    else:
        print("Model not recognized. OpenAI cost calculation failed.")

    return openai_cost


def rag(query, video_id,model='gpt-4o-mini'):
    t0 = time()
    search_results = search(query, video_id)
    prompt = build_prompt(query, search_results)
    answer, token_stats = llm(prompt, model=model)
    
    relevance, relevance_tokens = evaluate_relevance(query, answer)

    t1 = time()
    took = t1-t0

    openai_cost_rag = calculate_openai_cost(model, token_stats)
    openai_cost_eval = calculate_openai_cost(model, relevance_tokens)

    openai_cost = openai_cost_rag + openai_cost_eval

    answer_data = {
        "answer": answer,
        "model_used": model,
        "response_time": took,
        "relevance": relevance['Relevance'],
        "relevance_explanation": relevance['Explanation'],
        "prompt_tokens": token_stats['prompt_tokens'],
        "completion_tokens": token_stats['completion_tokens'],
        "total_tokens": token_stats['total_tokens'],
        "eval_prompt_tokens": relevance_tokens['prompt_tokens'],
        "eval_completion_tokens":relevance_tokens['completion_tokens'],
        "eval_total_tokens": relevance_tokens['total_tokens'],
        "openai_cost": openai_cost,
    }
    
    return answer_data
