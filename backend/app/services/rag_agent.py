# UPDATED rag_agent.py - PRESERVES ALL EXISTING FUNCTIONALITY
import os
from typing import TypedDict, Optional, List, Dict, Any
from langgraph.graph import StateGraph, END
from openai import OpenAI
import httpx
import json
import traceback
from dotenv import load_dotenv

# Import existing semantic cache and new tool registry
from app.services.semantic_rag_cache import SemanticRAGCache
from app.services.agentic_tools import tool_registry

load_dotenv()

redis_url = os.getenv("REDIS_URL")
semantic_cache = SemanticRAGCache(
    redis_url=redis_url, # type: ignore
    similarity_threshold=0.85 
)

# ENHANCED Agent State - adds agentic fields while keeping original ones
class AgentState(TypedDict):
    """Represents the state of our agent's conversation."""
    # Original fields
    user_query: str
    user_id: str
    source_filter: Optional[str]
    context: List[str]
    answer: str
    tool_call: Optional[Dict[str, Any]]
    action_performed: bool
    email_present: bool
    query_type: str
    
    # New agentic fields
    tool_calls: List[Dict[str, Any]]
    intermediate_results: List[Dict[str, Any]]
    execution_plan: List[str]
    confidence: float
    current_step: int
    max_steps: int

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
API_BASE_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN")
if not API_BASE_URL:
    API_BASE_URL = "http://localhost:8000"
else:
    API_BASE_URL = f"https://{API_BASE_URL}"

# --- ORIGINAL TOOL SCHEMA (preserved) ---
SEND_EMAIL_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "send_summary_email",
        "description": "Sends a summary or specific information via email to the currently authenticated user.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary_content": {"type": "string"},
                "recipient_email": {"type": "string"},
                "document_name": {"type": "string"}
            },
            "required": ["summary_content", "recipient_email"]
        }
    }
}

# --- ORIGINAL INTENT DETECTOR (preserved) ---
def intent_detector(state: AgentState) -> AgentState:
    """
    FIXED: Better context-aware intent detection
    """
    # Original cache check
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
    
    # IMPROVED classification prompt - more context-aware
    prompt = f"""
    You are an advanced assistant. Your primary task is RAG using the provided Context.

    Return EXACTLY one JSON object with one of these forms:

    1) If the question is clearly NOT related to the provided Context AND doesn't reference documents/files:
    {{"action": "general_query"}}

    2) If the user explicitly asked to email/send/share the result:
    {{"action": "email", "summary_content": "<concise summary>", "recipient_email": "<recipient email>", "document_name": "<optional>"}}

    3) If the question references "this document", "the file", "the PDF", or asks about content that might be in the context:
    {{"action": "answer", "answer": "<full answer text based on context>"}}

    4) If the question needs BOTH context AND external information (like current trends):
    {{"action": "agentic", "reasoning": "needs both document context and external search"}}

    IMPORTANT RULES:
    - If user says "this document", "the file", "PDF", or implies they're asking about uploaded content → ALWAYS use "answer"
    - Questions about "trending", "current", "latest" BUT referencing document content → use "agentic"
    - Only use "general_query" for pure knowledge questions like "capital of France"

    Context: {context_text}
    User request: {state['user_query']}

    Return JSON now:
    """

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role":"user", "content": prompt}],
            max_tokens=500,
            temperature=0.0
        )
        text = response.choices[0].message.content
        
        start = text.find("{") # type: ignore
        end = text.rfind("}") # type: ignore
        if start == -1 or end == -1:
            raise ValueError("LLM did not return JSON")
        json_text = text[start:end+1] # type: ignore
        obj = json.loads(json_text)

        action = obj.get("action")
        
        if action == "general_query":
            state["query_type"] = "GENERAL_QUERY"
            state["answer"] = ""
            state["tool_call"] = None
            return state
            
        elif action == "answer":
            state["answer"] = obj.get("answer", "Sorry, could not formulate an answer.")
            state["query_type"] = "RAG_ANSWER"
            try:
                semantic_cache.save(state['user_id'], state['source_filter'], state['user_query'], state["answer"]) # type: ignore
            except Exception as e:
                print("semantic_cache.save error:", e)
            state["tool_call"] = None
            return state

        elif action == "email":
            # Always email the authenticated user - no validation needed
            state["tool_call"] = {
                "summary_content": obj.get("summary_content", ""),
                "recipient_email": state['user_id'],  # Use authenticated user ID
                "document_name": obj.get("document_name", state.get("source_filter"))
            }
            state["query_type"] = "EMAIL_ACTION"
            return state

        elif action == "agentic":
            # NEW: Route to agentic processing for hybrid queries
            state["query_type"] = "AGENTIC_PLANNING"
            state["answer"] = ""
            return state
            
        else:
            state["answer"] = obj.get("answer") or "I could not decide; please rephrase."
            state["query_type"] = "RAG_ANSWER"
            return state

    except Exception as e:
        print("intent_detector LLM error:", e)
        # Fallback: assume RAG answer if there's context
        if state.get('context'):
            state["query_type"] = "RAG_ANSWER"
        else:
            state["query_type"] = "GENERAL_QUERY"
        
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

# --- ORIGINAL NODES (preserved) ---
def rag_process(state: AgentState) -> AgentState:
    """QUICK FIX: Handle missing answers gracefully"""
    state["action_performed"] = False
    
    # If no answer was formulated, create one
    if not state.get("answer") or state.get("answer") == "RAG path reached but no answer was formulated.":
        context_text = "\n".join(state.get("context", []))
        if context_text:
            state["answer"] = f"Based on the document: {context_text[:500]}..."  # Simple fallback
        else:
            state["answer"] = "I've processed your query but couldn't generate a specific answer from the available context."
    
    return state

def general_query_answer(state: AgentState) -> AgentState:
    """ORIGINAL: Generates answer to general, non-document query."""
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
    """ORIGINAL: Executes email sending API call."""
    tool_args = state.get("tool_call")
    if not tool_args:
        state["answer"] = "Error: Tool arguments were missing for the email action."
        state["action_performed"] = False
        return state

    summary_content = tool_args.get("summary_content", "Summary could not be generated.")
    recipient_email = tool_args.get("recipient_email", state["user_id"])
    document_name = tool_args.get("document_name", state["source_filter"] or "Relevant Documents")

    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                f"{API_BASE_URL}/api/actions/send_email",
                headers={"X-User-Id": state["user_id"]},
                 json={
                    "recipient_email": recipient_email,
                    "subject": f"Information from InsightSphere Agent",  # More descriptive
                    "body": f"""
                        {summary_content}

                        ---
                        This email was automatically generated by InsightSphere.
                        If you didn't request this summary, please ignore this email.
                    """.strip()
                }
            )
            response.raise_for_status() 
            action_result = response.json()
        
        state["answer"] = action_result['message'] 
        state["action_performed"] = True
        return state
    
    except Exception as e:
        state["answer"] = f"Agent Action Failed (Email): Could not execute sending function. Error: {e}"
        state["action_performed"] = False
        return state

# --- NEW AGENTIC NODES (added) ---
def agentic_planning_node(state: AgentState) -> AgentState:
    """NEW: Break complex queries into execution plan for agentic processing."""
    """NEW: Break complex queries into execution plan for agentic processing."""
    available_tools = list(tool_registry.tools.keys())
    
    planner_prompt = f"""
    Analyze this complex query and create a step-by-step execution plan.
    Available tools: {available_tools}
    
    Specialized Tools:
    - tavily_search: For real-time web search, latest news, market trends, current events
    - calculator: For mathematical calculations and computations  
    - sql_query: For internal business data queries
    
    Query: {state['user_query']}
    Context available: {len(state.get('context', []))} documents
    
    Return JSON with:
    - "steps": list of concrete steps to solve
    - "tools_needed": which tools to use
    - "complexity": "simple" | "medium" | "complex"
    
    Use tavily_search for any information that needs current/real-time data.
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": planner_prompt}],
            temperature=0.1,
            max_tokens=500
        )
        
        text = response.choices[0].message.content
        start = text.find("{") # type: ignore
        end = text.rfind("}") # type: ignore
        if start != -1 and end != -1:
            plan = json.loads(text[start:end+1]) # type: ignore
            state['execution_plan'] = plan.get('steps', [])
            state['intermediate_results'] = []
            state['current_step'] = 0
            state['max_steps'] = min(len(plan.get('steps', [])) + 2, 6)  # Limit steps
        else:
            # Fallback to simple processing
            state['execution_plan'] = []
            
    except Exception as e:
        print(f"Agentic planning error: {e}")
        state['execution_plan'] = []
        
    return state

# In the agentic_tool_node function, update the tool selection logic:

async def agentic_tool_node(state: AgentState) -> AgentState:
    """NEW: Execute tools for complex multi-step queries."""
    
    if not state['execution_plan'] or state['current_step'] >= len(state['execution_plan']):
        return state
        
    current_step_desc = state['execution_plan'][state['current_step']]
    
    # Updated tool selection logic with Tavily
    tool_to_use = None
    if any(word in current_step_desc.lower() for word in ['search', 'web', 'current', 'latest', 'trend', 'news', 'market']):
        tool_to_use = 'tavily_search'  # Changed from 'web_search'
    elif any(word in current_step_desc.lower() for word in ['calculat', 'math', 'compute', 'number']):
        tool_to_use = 'calculator'
    elif any(word in current_step_desc.lower() for word in ['data', 'database', 'query', 'sql']):
        tool_to_use = 'sql_query'
    
    if tool_to_use and tool_to_use in tool_registry.tools:
        try:
            # Parameter extraction for Tavily
            if tool_to_use == 'tavily_search':
                params = {"query": current_step_desc}
            elif tool_to_use == 'calculator':
                # Extract mathematical expressions
                import re
                math_expr = re.findall(r'[\d+\-*/().]+', current_step_desc)
                params = {"expression": math_expr[0] if math_expr else current_step_desc}
            else:
                params = {"query": current_step_desc}
            
            tool_function = tool_registry.tools[tool_to_use]['function']
            result = await tool_function(params)
            
            state['intermediate_results'].append({
                'step': state['current_step'],
                'tool': tool_to_use,
                'parameters': params,
                'result': result
            })
            
            print(f"🔧 Agentic tool executed: {tool_to_use} -> {result.get('success', False)}")
            
        except Exception as e:
            print(f"Tool execution error: {e}")
            state['intermediate_results'].append({
                'step': state['current_step'],
                'tool': tool_to_use,
                'error': str(e)
            })
    
    state['current_step'] += 1
    return state

def agentic_synthesis_node(state: AgentState) -> AgentState:
    """NEW: Synthesize final answer from agentic results."""
    
    if not state['intermediate_results']:
        return state
        
    context_text = "\n".join(state.get('context', []))
    intermediate_text = "\n".join([
        f"Step {i+1} ({res['tool']}): {str(res['result'])}" 
        for i, res in enumerate(state['intermediate_results'])
    ])
    
    synthesis_prompt = f"""
    Original query: {state['user_query']}
    
    Retrieved documents:
    {context_text}
    
    Tool results:
    {intermediate_text}
    
    Create a comprehensive answer combining all information.
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": synthesis_prompt}],
            temperature=0.3,
            max_tokens=800
        )
        
        state['answer'] = response.choices[0].message.content or state['answer']
        state['confidence'] = 0.8
        
    except Exception as e:
        print(f"Agentic synthesis error: {e}")
        
    return state

# --- ENHANCED ROUTING LOGIC ---
def route_intent(state: AgentState) -> str:
    """ENHANCED: Better routing for document-aware queries."""
    query_type = state.get("query_type")
    
    # Document-aware routing
    document_keywords = ['this document', 'the file', 'the pdf', 'uploaded', 'in the document']
    has_document_ref = any(keyword in state['user_query'].lower() for keyword in document_keywords)
    has_context = len(state.get('context', [])) > 0
    
    # Force RAG/agentic for document references
    if has_document_ref and has_context:
        # Check if it needs external data too
        if any(word in state['user_query'].lower() for word in ['trend', 'current', 'latest', 'now', '2024']):
            return "agentic_planning"
        else:
            return "rag_process"
    
    # Original routing logic for other cases
    if query_type == "AGENTIC_PLANNING":
        return "agentic_planning"
    elif query_type == "EMAIL_ACTION":
        return "email_action"
    elif query_type == "GENERAL_QUERY":
        return "general_query_answer"
    elif query_type in ["RAG_ANSWER", "ANSWER_FROM_CACHE", "DENIED"]:
        return "rag_process"
    else:
        return "rag_process"

def should_continue_agentic(state: AgentState) -> str:
    """Decide whether to continue agentic execution."""
    if (state['execution_plan'] and 
        state['current_step'] < len(state['execution_plan']) and 
        state['current_step'] < state['max_steps']):
        return "continue_agentic"
    else:
        return "agentic_synthesis"

# --- BUILD GRAPH WITH BOTH SYSTEMS ---
def build_enhanced_rag_agent():
    """Compiles the enhanced LangGraph with both original and agentic capabilities."""
    workflow = StateGraph(AgentState)

    # Add ORIGINAL nodes
    workflow.add_node("intent_detector", intent_detector)
    workflow.add_node("rag_process", rag_process)
    workflow.add_node("email_action", email_action)
    workflow.add_node("general_query_answer", general_query_answer)

    # Add NEW agentic nodes
    workflow.add_node("agentic_planning", agentic_planning_node)
    workflow.add_node("agentic_tool", agentic_tool_node)
    workflow.add_node("agentic_synthesis", agentic_synthesis_node)

    # Set entry point (original)
    workflow.set_entry_point("intent_detector")

    # ORIGINAL routing
    workflow.add_conditional_edges(
        "intent_detector",
        route_intent, 
        {
            "email_action": "email_action", 
            "rag_process": "rag_process",
            "general_query_answer": "general_query_answer",
            "agentic_planning": "agentic_planning"  # New route
        }
    )
    
    # AGENTIC workflow
    workflow.add_edge("agentic_planning", "agentic_tool")
    workflow.add_conditional_edges(
        "agentic_tool",
        should_continue_agentic,
        {
            "continue_agentic": "agentic_tool",
            "agentic_synthesis": "agentic_synthesis"
        }
    )
    workflow.add_edge("agentic_synthesis", "rag_process")  # Rejoin main flow

    # ORIGINAL direct edges to END
    workflow.add_edge("rag_process", END)
    workflow.add_edge("email_action", END)
    workflow.add_edge("general_query_answer", END)

    return workflow.compile()

# Initialize the enhanced agent
RAG_AGENT_APP = build_enhanced_rag_agent()