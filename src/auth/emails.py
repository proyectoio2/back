import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from typing import Optional
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import ssl

from src.config import get_settings

settings = get_settings()


class EmailService:
    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = 465
        self.sender_email = settings.SENDER_EMAIL
        self.sender_password = settings.SMTP_PASSWORD
        self.template_dir = Path(__file__).parent.parent / "templates" / "email"
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=True
        )

    async def _send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        try:
            msg = MIMEMultipart()
            msg["From"] = self.sender_email
            msg["To"] = to_email
            msg["Subject"] = subject

            msg.attach(MIMEText(html_content, "html"))

            context = ssl.create_default_context()
            smtp = aiosmtplib.SMTP(
                hostname=self.smtp_server,
                port=self.smtp_port,
                use_tls=True,
                tls_context=context
            )
            
            await smtp.connect()
            await smtp.login(self.sender_email, self.sender_password)
            await smtp.send_message(msg)
            await smtp.quit()
            return True
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            return False

    async def send_welcome_email(self, to_email: str, username: str) -> bool:
        template = self.env.get_template("welcome.html")
        html_content = template.render(username=username)
        return await self._send_email(
            to_email=to_email,
            subject="¡Bienvenido a nuestra plataforma!",
            html_content=html_content
        )

    async def send_password_reset_email(self, to_email: str, reset_token: str) -> bool:
        base_url = f"https://{settings.URL}" if not settings.URL.startswith('http') else settings.URL
        reset_url = f"{base_url}/auth/password-reset?token={reset_token}"
        
        template = self.env.get_template("password_reset.html")
        html_content = template.render(
            reset_url=reset_url,
            expiration_minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        )
        return await self._send_email(
            to_email=to_email,
            subject="Restablecimiento de contraseña",
            html_content=html_content
        )
