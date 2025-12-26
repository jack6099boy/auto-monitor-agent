import os
import smtplib
from email.mime.text import MIMEText
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class NotificationManager:
    def __init__(self):
        self.slack_token = os.getenv('SLACK_BOT_TOKEN')
        self.slack_channel = os.getenv('SLACK_CHANNEL', '#alerts')
        self.email_server = os.getenv('EMAIL_SERVER', 'smtp.gmail.com')
        self.email_port = int(os.getenv('EMAIL_PORT', 587))
        self.email_user = os.getenv('EMAIL_USER')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.email_to = os.getenv('EMAIL_TO')

        self.slack_client = WebClient(token=self.slack_token) if self.slack_token else None

    def send_slack_alert(self, message: str) -> bool:
        if not self.slack_client:
            print("Slack client not configured.")
            return False
        try:
            response = self.slack_client.chat_postMessage(
                channel=self.slack_channel,
                text=message
            )
            return response['ok']
        except SlackApiError as e:
            print(f"Slack API error: {e}")
            return False

    def send_email_alert(self, message: str) -> bool:
        if not all([self.email_user, self.email_password, self.email_to]):
            print("Email configuration incomplete.")
            return False
        try:
            msg = MIMEText(message)
            msg['Subject'] = 'AutoTest AIOps Agent Alert'
            msg['From'] = self.email_user
            msg['To'] = self.email_to

            server = smtplib.SMTP(self.email_server, self.email_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            server.sendmail(self.email_user, self.email_to, msg.as_string())
            server.quit()
            return True
        except Exception as e:
            print(f"Email send error: {e}")
            return False

    def send_alert(self, message: str, channels: list = None) -> dict:
        if channels is None:
            channels = ['slack', 'email']
        results = {}
        if 'slack' in channels:
            results['slack'] = self.send_slack_alert(message)
        if 'email' in channels:
            results['email'] = self.send_email_alert(message)
        return results