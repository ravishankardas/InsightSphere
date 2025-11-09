# In your query endpoint
def validate_query(query: str) -> tuple[bool, str]:
    """Basic query validation"""
    
    # Length limits
    if len(query) > 1000:
        return False, "Query too long (max 1000 characters)"
    
    if len(query.strip()) == 0:
        return False, "Query cannot be empty"
    
    # Basic toxicity filter
    toxic_phrases = [
        "ignore previous", "forget everything", "system prompt",
        "as an ai", "you are now", "role play", "pretend you are"
    ]
    
    query_lower = query.lower()
    for phrase in toxic_phrases:
        if phrase in query_lower:
            return False, "Query contains restricted phrases"
    
    return True, ""



def sanitize_response(response: str) -> str:
    """Basic response sanitization"""
    # Remove any potential HTML/JS injection
    import html
    response = html.escape(response)
    
    # Truncate extremely long responses
    if len(response) > 10000:
        response = response[:10000] + "... [response truncated]"
    
    return response

