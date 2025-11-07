from email.mime.multipart import MIMEMultipart
import os
import smtplib 
from email.mime.text import MIMEText
from fastapi import APIRouter, Header, HTTPException
from typing import Optional, Dict
from icecream import ic

from dotenv import load_dotenv
load_dotenv()


router = APIRouter()

# --- Email Placeholder Configuration ---


import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from sendgrid import SendGridAPIClient # type: ignore
from sendgrid.helpers.mail import Mail # type: ignore
from app.logger import setup_logger
logger = setup_logger()


SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", SMTP_USER)



def send_email_action(recipient_email: str, subject: str, body: str):
    message = Mail(
        from_email=SENDER_EMAIL,
        to_emails=recipient_email,
        subject=subject,
        plain_text_content=body)
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        # sg.set_sendgrid_data_residency("eu")
        # uncomment the above line if you are sending mail using a regional EU subuser
        response = sg.send(message)
        logger.info(f"✅ Email sent to {recipient_email} from {SENDER_EMAIL} via {SMTP_SERVER}:{SMTP_PORT}")
        return True
        # print(response.status_code)
        # print(response.body)
        # print(response.headers)
    except Exception as e:
        logger.error("❌ Failed to send email:", type(e).__name__, e)
        return False
    

@router.post("/send_email")
async def send_email_action_endpoint(
    data: Dict[str, str],
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """
    API endpoint called by the agent (rag_agent.py) to send the summary email.
    """
    recipient_email = data.get("recipient_email")
    subject = data.get("subject", "InsightSphere Summary Request")
    # Add a simple closing to the email body for professionalism
    body = f"Hello, below is the information you asked:\n\n{data.get('body', 'No content provided.')}\n\n---\nBest regards,\nInsightSphere Agent"

    if not user_id:
        raise HTTPException(status_code=401, detail="User ID is required.")

    # Security check: Ensure the agent is only emailing the authenticated user
    if not recipient_email or recipient_email != user_id:
        raise HTTPException(
            status_code=400, 
            detail="Recipient email must match the authenticated user's ID for security."
        )

    success = send_email_action(recipient_email, subject, body)

    if success:
        return {"status": "success", "message": f"✅ Action performed: Email sent successfully to {recipient_email}."}
    else:
        return {"status": "failure", "message": "❌ Action failed: Email server configuration error."}
