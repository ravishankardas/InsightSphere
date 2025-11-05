
# ---- Quick example usage ----
from intent_classifier import detect_email_intent


if __name__ == "__main__":
    tests = [
        "Please send an email to hr@company.com: Subject - Interview reschedule. Tell them I need to move to next Tuesday.",
        "How do I create a new folder in Gmail?",
        "Draft an email to my manager asking for feedback, don't send it yet.",
        "Can you email john@example.com that the meeting is cancelled?",
        "can you send me an email?"
    ]

    for t in tests:
        print("QUERY:", t)
        out = detect_email_intent(t)
        # Use out.json(indent=2) for clean, readable output
        print("RESULT:", out, "\n")