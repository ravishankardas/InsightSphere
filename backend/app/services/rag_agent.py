import os
from typing import TypedDict, Optional, List, Dict, Any
# You need to install the LangGraph package: pip install langgraph
from langgraph.graph import StateGraph, END 
from openai import OpenAI
import httpx # You need to install httpx for making API calls: pip install httpx
import json
# Assuming app.services.semantic_rag_cache is available
from app.services.semantic_rag_cache import SemanticRAGCache
from dotenv import load_dotenv
import traceback

load_dotenv()

# --- 1. Define the Agent State ---

redis_url=os.getenv("REDIS_URL")
semantic_cache = SemanticRAGCache(
    redis_url=redis_url, # type: ignore
    similarity_threshold=0.85 
)

# This dictionary structure is the single source of truth passed between nodes.
class AgentState(TypedDict):
    """Represents the state of our agent's conversation."""
    user_query: str
    user_id: str
    source_filter: Optional[str]
    context: List[str] # Retrieved document chunks from the retrieval step
    answer: str
    tool_call: Optional[Dict[str, Any]]
    action_performed: bool # Flag for frontend/cache logic
    email_present: bool
    # NEW FIELD: To store the classification result
    query_type: str 

# --- 2. Initialize LLM Client ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
# NOTE: Update this URL to match your deployment URL in production for the agent to find the FastAPI endpoint
# API_BASE_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000") 
API_BASE_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN")
if not API_BASE_URL:
    API_BASE_URL = "http://localhost:8000"
else:
    API_BASE_URL = f"https://{API_BASE_URL}"


# --- 3. Tool Schema (Used by Intent Detector) ---
SEND_EMAIL_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "send_summary_email",
        "description": "Sends a summary or specific information via email to the currently authenticated user. Use this tool ONLY if the user explicitly asks to EMAIL, SEND, or SHARE the information with themselves.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary_content": {
                    "type": "string",
                    "description": "The full, concise summary or answer content generated based on the context."
                },
                "recipient_email": {
                    "type": "string",
                    "description": "The email address of the recipient. MUST be the user_id provided in the state."
                },
                "document_name": {
                    "type": "string",
                    "description": "The name of the document being summarized (if known from source_filter)."
                }
            },
            "required": ["summary_content", "recipient_email"]
        }
    }
}

# --- 4. Graph Nodes (Logic Functions) ---

def intent_detector(state: AgentState) -> AgentState:
    """
    Determine whether to (a) answer from context, (b) request an email send,
    or (c) classify the query as general knowledge (not related to RAG docs).
    """
    # 1) quick cache check
    if not state.get("email_present") and semantic_cache:
        try:
            cached_answer = semantic_cache.search(state["user_id"], state["source_filter"], state["user_query"]) # type: ignore
            if cached_answer:
                state["answer"] = cached_answer
                state["query_type"] = "ANSWER_FROM_CACHE"
                return state
        except Exception as e:
            print("semantic_cache.search error:", e)

    context_text = "\n---\n".join(state.get("context", [])) or ""
    
    # --- Classification and Tool/Answer Prompt ---
    # This single prompt handles all routing decisions: General, Email, or RAG Answer
    prompt = f"""
            You are an advanced assistant. Your primary task is RAG (Retrieval Augmented Generation) 
            using the provided Context, but you can also handle general questions or execute actions.

            Return EXACTLY one JSON object (no explanatory text) with one of these forms:

            1) If the question is clearly NOT related to the provided Context (e.g., "What is the capital of France?", "Tell me a joke"):
            {{"action": "general_query"}}

            2) If the user explicitly asked to email/send/share the result (and the question IS RAG-relevant):
            {{"action": "email", "summary_content": "<concise summary to email>", "recipient_email": "<recipient email, MUST be the user's id/email>", "document_name": "<optional document name>"}}

            3) If the question is RAG-relevant and NOT an email request:
            {{"action": "answer", "answer": "<full answer text based on context>"}}


            Rules:
            - The presence of the Context is the key indicator for RAG-relevance. If the question can only be answered by *general knowledge* and not the specific documents, choose "general_query".
            - Only choose "email" if the user explicitly asked to EMAIL/SHARE/SEND to themselves.
            - The user's id/email is: {state['user_id']}

            Context:
            {context_text}

            User request:
            {state['user_query']}

            Return JSON now:
"""

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role":"user", "content": prompt}],
            max_tokens=500,
            temperature=0.0
        )
        text = response.choices[0].message.content  # adapt if SDK differs
        
        start = text.find("{") # type: ignore
        end = text.rfind("}") # type: ignore
        if start == -1 or end == -1:
            raise ValueError("LLM did not return JSON")
        json_text = text[start:end+1] # type: ignore
        obj = json.loads(json_text)

        action = obj.get("action")
        
        if action == "general_query":
            state["query_type"] = "GENERAL_QUERY"
            state["answer"] = "" # Clear answer for the next node to generate it
            state["tool_call"] = None
            return state
            
        elif action == "answer":
            state["answer"] = obj.get("answer", "Sorry, could not formulate an answer.")
            state["query_type"] = "RAG_ANSWER"
            # cache the answer for future
            try:
                semantic_cache.save(state['user_id'], state['source_filter'], state['user_query'], state["answer"]) # type: ignore
            except Exception as e:
                print("semantic_cache.save error:", e)
            state["tool_call"] = None
            return state

        elif action == "email":
            # Validate recipient (Security check)
            recipient = obj.get("recipient_email")
            if recipient != state.get("user_id"):
                state["answer"] = "Denied: recipient email must match your account email."
                state["action_performed"] = False
                state["query_type"] = "DENIED"
                return state

            # Populate tool_call with validated args
            state["tool_call"] = {
                "summary_content": obj.get("summary_content", ""),
                "recipient_email": recipient,
                "document_name": obj.get("document_name", state.get("source_filter"))
            }
            state["query_type"] = "EMAIL_ACTION"
            return state
            
        else:
            # fallback: treat as direct answer if unclear
            state["answer"] = obj.get("answer") or "I could not decide; please rephrase."
            state["query_type"] = "RAG_ANSWER"
            return state

    except Exception as e:
        # Robust fallback: If JSON parsing fails, assume RAG answer and use a simple generation prompt
        print("intent_detector LLM error:", e)
        print(traceback.format_exc())
        state["query_type"] = "RAG_ANSWER" # Fallback to RAG path
        
        try:
            fallback = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                  {"role":"system", "content":"You are a helpful assistant that answers using the context below."},
                  {"role":"user", "content": f"Context:\n{context_text}\n\nUser: {state['user_query']}"}
                ],
                max_tokens=400,
                temperature=0.0
            )
            state["answer"] = fallback.choices[0].message.content # type: ignore
            try:
                semantic_cache.save(state['user_id'], state.get('source_filter'), state['user_query'], state["answer"]) # type: ignore
            except Exception:
                pass
            return state
        except Exception as e2:
            state["answer"] = f"Error generating response: {e2}"
            return state


def rag_process(state: AgentState) -> AgentState:
    """
    Finalizes the RAG output. If the intent detector classified it as RAG 
    (and didn't cache), the answer is already in state['answer'] from the detector.
    """
    state["action_performed"] = False
    # If the answer was generated in the fallback, we ensure action is false and end.
    if state.get("query_type") in ["RAG_ANSWER", "ANSWER_FROM_CACHE", "DENIED"]:
        return state
    # If we somehow reached here without an answer, use a placeholder
    state["answer"] = "RAG path reached but no answer was formulated. Please check the intent_detector logic."
    return state


def general_query_answer(state: AgentState) -> AgentState:
    """
    Generates an answer to a general, non-document query without any RAG context.
    """
    print("🌍 General Query Node: Answering without context...")
    
    general_prompt = f"You are a helpful and knowledgeable general assistant. Answer the user's question concisely using only your general knowledge. User Query: {state['user_query']}"
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role":"user", "content": general_prompt}],
            max_tokens=400,
            temperature=0.7 
        )
        state["answer"] = response.choices[0].message.content # type: ignore
        state["action_performed"] = False
        return state
    except Exception as e:
        state["answer"] = f"Error generating general response: {e}"
        state["action_performed"] = False
        return state


async def email_action(state: AgentState) -> AgentState:
    """
    Executes the email sending API call by calling the new FastAPI endpoint.
    """
    tool_args = state.get("tool_call")
    if not tool_args:
        state["answer"] = "Error: Tool arguments were missing for the email action."
        state["action_performed"] = False
        return state

    summary_content = tool_args.get("summary_content", "Summary could not be generated.")
    recipient_email = tool_args.get("recipient_email", state["user_id"])
    document_name = tool_args.get("document_name", state["source_filter"] or "Relevant Documents")

    try:
        print(f"{API_BASE_URL}/api/actions/send_email",)
        # Use httpx.AsyncClient with timeout
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                f"{API_BASE_URL}/api/actions/send_email",
                headers={"X-User-Id": state["user_id"]},
                json={
                    "recipient_email": recipient_email,
                    "subject": f"Hello from Insightsphere",
                    "body": summary_content
                }
            )
            response.raise_for_status() 
            action_result = response.json()
        
        # The answer will be the message from the email API endpoint (e.g., success message)
        state["answer"] = action_result['message'] 
        state["action_performed"] = True
        return state
    
    except Exception as e:
        # If the API call fails
        state["answer"] = f"Agent Action Failed (Email): Could not execute sending function. Error: {e}"
        state["action_performed"] = False
        return state


# --- 5. Build the LangGraph Application ---

def route_intent(state: AgentState) -> str:
    """
    Chooser function: determines next node based on the query_type set in the intent_detector.
    """
    query_type = state.get("query_type")
    
    if query_type == "EMAIL_ACTION":
        return "email_action"
    elif query_type == "GENERAL_QUERY":
        return "general_query_answer"
    elif query_type in ["RAG_ANSWER", "ANSWER_FROM_CACHE", "DENIED"]:
        # RAG is the default path for answers formulated or already retrieved
        return "rag_process"
    else:
        # Fallback to RAG if classification failed
        return "rag_process"
    
def build_rag_agent():
    """Compiles the LangGraph state machine."""
    workflow = StateGraph(AgentState)

    # 1. Add nodes
    workflow.add_node("intent_detector", intent_detector)
    workflow.add_node("rag_process", rag_process) # Handles RAG-relevant answers
    workflow.add_node("email_action", email_action) # Action Execution node
    workflow.add_node("general_query_answer", general_query_answer) # NEW NODE

    # 2. Set entry point
    workflow.set_entry_point("intent_detector")

    # 3. Conditional edge: From intent_detector to the appropriate next step
    workflow.add_conditional_edges(
        "intent_detector",
        route_intent, 
        {
            "email_action": "email_action", 
            "rag_process": "rag_process",
            "general_query_answer": "general_query_answer" # New edge for general queries
        }
    )
    
    # 4. Direct edges to END
    workflow.add_edge("rag_process", END)
    workflow.add_edge("email_action", END)
    workflow.add_edge("general_query_answer", END) # New edge from the general answer node

    # Compile the graph
    app = workflow.compile()
    return app

# Initialize the agent once at startup
RAG_AGENT_APP = build_rag_agent()