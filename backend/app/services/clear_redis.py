import redis # type: ignore
import os
from dotenv import load_dotenv

# Load environment variables (assuming your Redis config is in your .env file)
load_dotenv()

# --- Configuration ---
# Use environment variables for connection details for security
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
# Set a timeout for the connection
TIMEOUT = 5 

def clear_all_redis_keys():
    """
    Connects to Redis and removes ALL keys from ALL databases.
    WARNING: This is a destructive operation!
    """
    print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
    
    try:
        # Initialize the Redis client
        r = redis.Redis(
            host=REDIS_HOST, 
            port=REDIS_PORT, 
            password=REDIS_PASSWORD, 
            socket_timeout=TIMEOUT,
            decode_responses=True # Decode responses to strings
        )

        # Ping the server to check the connection
        r.ping()
        print("Connection successful.")

        # --- DANGER ZONE: EXECUTE FLUSHALL ---
        confirmation = input(
            "\n⚠️ WARNING: This will DELETE ALL keys in ALL databases! "
            "Are you sure you want to proceed? (type 'YES' to confirm): "
        )

        if confirmation.strip().upper() == "YES":
            # Execute the FLUSHALL command
            r.flushall()
            print("\n✅ Success: All keys have been removed from all Redis databases.")
        else:
            print("\nOperation cancelled. No keys were deleted.")

    except redis.exceptions.ConnectionError as e:
        print(f"\n❌ Connection Error: Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}.")
        print(f"Details: {e}")
    except redis.exceptions.AuthenticationError:
        print("\n❌ Authentication Error: Invalid Redis password.")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")


if __name__ == "__main__":
    clear_all_redis_keys()