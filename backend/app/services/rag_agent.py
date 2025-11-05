import os
from typing import TypedDict, Optional, List, Dict, Any
# You need to install the LangGraph package: pip install langgraph
from langgraph.graph import StateGraph, END 
from openai import OpenAI
import httpx # You need to install httpx for making API calls: pip install httpx
import json
from dotenv import load_dotenv
load_dotenv()

# --- 1. Define the Agent State ---
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

# --- 2. Initialize LLM Client ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
# NOTE: Update this URL to match your deployment URL in production for the agent to find the FastAPI endpoint
API_BASE_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000") 
# API_BASE_URL = "http://localhost:8000"



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
    Decides the next step: RAG or EMAIL action using OpenAI's function calling.
    Updates the state with either 'answer' or 'tool_call'.
    """
    context_text = "\n---\n".join(state["context"])
    
    messages = [
        {"role": "system", "content": f"You are an assistant who can perform two actions: either answer the user's question based on the provided context, or call the 'send_summary_email' tool if the user explicitly asks to email, send, or share the information with themselves. The user's ID/email is {state['user_id']}. Always use this email for the recipient_email argument if a tool call is needed."},
        {"role": "user", "content": f"Based on this context:\n---\n{context_text}\n---\n\nUser's Request: {state['user_query']}"}
    ]

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages, # type: ignore
        tools=[SEND_EMAIL_TOOL_SCHEMA], # type: ignore
        tool_choice="auto", 
        max_tokens=500
    )

    # CHECK FOR TOOL_CALLS ON THE MESSAGE OBJECT
    if response.choices[0].message.tool_calls:
        # LLM decided to call a function
        # ACCESS tool_calls ON THE MESSAGE OBJECT
        tool_call = response.choices[0].message.tool_calls[0] # type: ignore
        func_args = json.loads(tool_call.function.arguments)
        
        state["tool_call"] = func_args
    else:
        # LLM decided to answer directly (Standard RAG)
        state["answer"] = response.choices[0].message.content # type: ignore
        
    return state


def rag_process(state: AgentState) -> AgentState:
    """
    Finalizes the RAG output. If the intent detector didn't call a tool, 
    the answer is already in state['answer'] from the LLM call in the detector.
    """
    # print("rag_process called with state:", state)
    # The answer is already populated by the intent_detector LLM call
    state["action_performed"] = False
    return state


async def email_action(state: AgentState) -> AgentState:
    """
    Executes the email sending API call by calling the new FastAPI endpoint.
    """
    # print("email_action called with state:", state)
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
    Chooser function: determines next node based on state. 
    It checks if the intent_detector set a tool_call in the state.
    """
    if state.get("tool_call"):
        return "email_action"
    else:
        return "rag_process"
    
def build_rag_agent():
    """Compiles the LangGraph state machine."""
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("intent_detector", intent_detector)
    workflow.add_node("rag_process", rag_process) # Final RAG output node
    workflow.add_node("email_action", email_action) # Action Execution node

    # Set entry point
    workflow.set_entry_point("intent_detector")

    # Conditional edge: From intent_detector to the appropriate next step
    # Now intent_detector returns the updated state, and route_intent determines the next step.
    workflow.add_conditional_edges(
        "intent_detector",
        route_intent, 
        {"email_action": "email_action", "rag_process": "rag_process"}
    )
    
    # Direct edges to END
    workflow.add_edge("rag_process", END)
    workflow.add_edge("email_action", END)

    # Compile the graph
    app = workflow.compile()
    return app

# Initialize the agent once at startup
RAG_AGENT_APP = build_rag_agent()