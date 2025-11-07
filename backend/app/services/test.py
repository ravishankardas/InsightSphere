# # import os
# # import resend # type: ignore
# # from dotenv import load_dotenv
# # load_dotenv()

# # resend.api_key = os.environ["RESEND_API_KEY"]

# # params: resend.Emails.SendParams = {
# #     "from": "InsightSphere <theinsightsphere.xyz>",
# #     "to": ["ravishankerdas1998@gmail.com"],
# #     "subject": "Hello from InsightSphere",
# #     "html": "<strong>it works!</strong>",
# # }

# # email = resend.Emails.send(params)
# # print(email)


# # import os
# # from sendgrid import SendGridAPIClient
# # from sendgrid.helpers.mail import Mail
# # from dotenv import load_dotenv
# # load_dotenv()

# # message = Mail(
# #     from_email='ravishankerdas020@gmail.com',
# #     to_emails='ravishankerdas1998@gmail.com',
# #     subject='Hello from insightsphere',
# #     html_content='<strong>Hello, please find the attached resume as requested</strong>')
# # try:
# #     sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
# #     # sg.set_sendgrid_data_residency("eu")
# #     # uncomment the above line if you are sending mail using a regional EU subuser
# #     response = sg.send(message)
# #     print(response.status_code)
# #     print(response.body)
# #     print(response.headers)
# #     print("Email sent successfully.")
# # except Exception as e:
# #     print(e.message)

# # from ..api.send_email_action import send_email_action
# import os
# import smtplib
# from email.mime.multipart import MIMEMultipart
# from email.mime.text import MIMEText
# from dotenv import load_dotenv
# load_dotenv()

# SMTP_SERVER = os.getenv("SMTP_SERVER")
# SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
# SMTP_USER = os.getenv("SMTP_USER")
# SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
# SENDER_EMAIL = os.getenv("SENDER_EMAIL", SMTP_USER)

# def send_email_action(recipient_email: str, subject: str, body: str) -> bool:
#     if not all([SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD]):
#         print("⚠️ Email config missing (SMTP_SERVER, SMTP_USER, SMTP_PASSWORD).")
#         return True  # keep previous behavior for development; change to False if you want stricter checks

#     msg = MIMEMultipart()
#     msg['From'] = SENDER_EMAIL # type: ignore
#     msg['To'] = recipient_email
#     msg['Subject'] = subject
#     msg.attach(MIMEText(body, 'plain'))

#     try:
#         # If port 465 -> use SMTP_SSL, otherwise use starttls on 587 (recommended)
#         if SMTP_PORT == 465:
#             server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30) # type: ignore
#             server.ehlo()
#         else:
#             server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) # type: ignore
#             server.ehlo()
#             server.starttls()
#             server.ehlo()

#         # Use the SMTP_USER and SMTP_PASSWORD from env
#         server.login(SMTP_USER, SMTP_PASSWORD) # type: ignore
#         server.sendmail(SENDER_EMAIL, [recipient_email], msg.as_string()) # type: ignore
#         server.quit()
#         print(f"✅ Email sent to {recipient_email} from {SENDER_EMAIL} via {SMTP_SERVER}:{SMTP_PORT}")
#         return True

#     except smtplib.SMTPAuthenticationError as auth_err:
#         # Common: bad credentials, app password needed, account blocked
#         print("❌ SMTP Authentication failed:", auth_err)
#         print("→ If using Gmail, ensure you created an App Password (if your account has 2FA).")
#         print("→ If you recently changed your Google password, regenerate an App Password.")
#         return False

#     except Exception as e:
#         print("❌ Failed to send email:", type(e).__name__, e)
#         return False
    
# recipient_email = "ravishankerdas020@gmail.com"
# subject = "Hello from InsightSphere"
# body = "it works!"

# success = send_email_action(recipient_email, subject, body)
# if success:
#     print("Email sent successfully.")














# # from rag_agent import build_rag_agent
# # from IPython.display import display, Image

# # def draw_graph(app):
# #     display(Image(app.get_graph().draw_mermaid_png()))

# # rag_agent = build_rag_agent()

# # draw_graph(rag_agent)