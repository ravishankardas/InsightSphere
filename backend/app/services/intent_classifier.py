from typing import Optional, Literal
import os

from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnablePassthrough
from dotenv import load_dotenv

load_dotenv()


# ---- Pydantic model for the structured output ----
class IntentResult(BaseModel):
    # Whether the user intends to send an email now
    send_email: bool
    # A short label of intent for readability
    intent: Literal["send_email", "not_send_email"]
    # If an email should be sent, best-effort extracted recipient (may be None)
    recipient: Optional[str] = None
    # If an email should be sent, best-effort extracted subject (may be None)
    subject: Optional[str] = None
    # Short explanation of why the classifier chose that label
    reason: Optional[str] = None

# ---- Prompt + parser ----
parser = JsonOutputParser(pydantic_object=IntentResult)

PROMPT = PromptTemplate(
    input_variables=["query"],
    template="""
You are a classifier that decides whether a user's text is an **explicit request to send, draft, or compose an email** (an instruction to perform an email action on their behalf) 
or NOT (general question, chat, scheduling, or help composing without a send instruction).

Return a JSON that follows the schema exactly and nothing else.

Criteria for send_email=True:
- **Mail Action:** The user is clearly asking to perform an action related to sending an email, such as "mail this to X", "send it to Y", "email me the summary", or "draft and send a message".
- **Extraction:** If send_email=True, attempt a best-effort extraction of the recipient and subject.

Criteria for send_email=False:
- **General Inquiry:** The query is about email settings, how to use Gmail, or a general request not related to *sending* new mail.
- **Draft Only:** The user explicitly states they only want to *draft* or *compose* an email but not send it yet.

Query:
{query}

PARSER_INSTRUCTIONS:
{format_instructions}
"""
).partial(format_instructions=parser.get_format_instructions())

# ---- Main function ----
def detect_email_intent(
    query: str,
    model_name: str = "gpt-4o-mini"
) -> IntentResult:
    """
    Return IntentResult for the provided query.
    """
    openai_api_key = os.getenv("OPENAI_API_KEY")
    
    # NOTE: Ensure your OPENAI_API_KEY is set in the environment or a .env file
    llm = ChatOpenAI(model=model_name, api_key=openai_api_key, temperature=0)  # type: ignore

    # Build the LangChain Expression Language (LCEL) chain
    chain = (
        {"query": RunnablePassthrough()}
        | PROMPT
        | llm
        | parser
    )

    # Run the chain using the input query
    result = chain.invoke(query)
    
    return result