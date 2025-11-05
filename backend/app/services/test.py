from langcache import LangCache # type: ignore
from dotenv import load_dotenv
import os
load_dotenv()

api_key = os.getenv("LANGCACHE_API_KEY", "")

with LangCache(
    server_url=os.getenv("LANGCACHE_SERVER_URL", ""),
    cache_id=os.getenv("LANGCACHE_CACHE_ID", ""),
    api_key=api_key,
) as lang_cache:

    prompt="How does love work?",
    user_id="user_123",
    file_name="document.pdf"
    final_prompt = f"{user_id} + {file_name} + {prompt}"

    # save_response = lang_cache.set(
    #     prompt=final_prompt,
    #     response="Semantic caching stores and retrieves data based on meaning, not exact matches.",

    # )
    # print("Save entry response:", save_response)

    # Search for entries
    search_response = lang_cache.search(
        prompt=final_prompt
    )
    if search_response.data:
        print("Search entry response:", search_response)
        print("Search entry response:", search_response.data[0].response)
    else:
        print("No matching entries found.")