import imaplib
import email
import time
from datetime import datetime
import ssl
import os
import mimetypes
import configparser
import subprocess
import logging
from email.message import Message
from typing import List, Dict, Optional, Any
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class Raio:
    """
    A class to monitor an email inbox and process incoming messages and attachments.
    Supports image display functionality for received image attachments.
    """
    
    # Default configuration
    DEFAULT_CONFIG = {
        "IMAP": {
            "port": "143",
            "server": "",
            "email": "",
            "password": ""
        }
    }

    def __init__(self):
        """Initialize Raio email monitor."""
        logging.info("Raio started")
        self.config = self.load_config()
        self.attachments_dir = Path("attachments")
        self.attachments_dir.mkdir(exist_ok=True)

    def load_config(self) -> configparser.ConfigParser:
        """
        Load configuration from config.ini file or create it if it doesn't exist.
        
        Returns:
            configparser.ConfigParser: Loaded configuration
        """
        config = configparser.ConfigParser()
        config_file = Path("config.ini")

        if not config_file.exists():
            logging.info("Configuration file not found. Starting setup...")
            config["IMAP"] = {
                "server": input("Enter IMAP server (e.g., imap.example.com): ").strip(),
                "port": input("Enter IMAP port (default 143): ").strip() or "143",
                "email": input("Enter your email address: ").strip(),
                "password": input("Enter your email password: ").strip()
            }
            
            with config_file.open("w") as file:
                config.write(file)
            logging.info(f"Configuration saved to {config_file}")
        else:
            config.read(config_file)

        return config

    def create_imap_connection(self) -> imaplib.IMAP4:
        """
        Create and return an authenticated IMAP connection.
        
        Returns:
            imaplib.IMAP4: Authenticated IMAP connection
        
        Raises:
            Exception: If connection or authentication fails
        """
        try:
            imap_settings = self.config["IMAP"]
            imap_server = imaplib.IMAP4(
                imap_settings["server"],
                int(imap_settings["port"])
            )

            # Create SSL context (Note: Should be properly configured in production)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            # Login to server
            imap_server.login(imap_settings["email"], imap_settings["password"])
            return imap_server
        except Exception as e:
            logging.error(f"Failed to create IMAP connection: {e}")
            raise

    def process_attachment(self, part: Message, uid: str) -> Dict[str, str]:
        """
        Process and save email attachment.
        
        Args:
            part: Email message part containing the attachment
            uid: Unique identifier for the email
            
        Returns:
            Dict containing attachment metadata
        """
        filename = f"mail{uid}_{part.get_filename()}"
        filepath = self.attachments_dir / filename
        
        with filepath.open("wb") as f:
            f.write(part.get_payload(decode=True))
            
        return {
            "filename": filename,
            "filepath": str(filepath),
            "mimetype": mimetypes.guess_type(str(filepath))[0]
        }

    def extract_email_content(self, msg: Message, uid: str) -> tuple:
        """
        Extract content from email message including body and attachments.
        
        Args:
            msg: Email message
            uid: Unique identifier for the email
            
        Returns:
            tuple: (body, attachments)
        """
        body = ""
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if content_type == "text/plain" and "attachment" not in content_disposition:
                    body = part.get_payload(decode=True)
                    if body:
                        body = body.decode()

                elif "attachment" in content_disposition or part.get_filename():
                    attachments.append(self.process_attachment(part, uid))
        else:
            body = msg.get_payload(decode=True)
            if body:
                body = body.decode()

        return body, attachments

    def check_emails(self):
        """Check for new emails and process them."""
        try:
            imap_server = self.create_imap_connection()
            imap_server.select('INBOX')

            status, messages = imap_server.search(None, 'ALL')
            if status != "OK":
                logging.error("Failed to search messages")
                return

            for mail_id in messages[0].split():
                try:
                    self.process_single_email(imap_server, mail_id)
                except Exception as e:
                    logging.error(f"Error processing email {mail_id}: {e}")

            imap_server.close()
            imap_server.logout()

        except Exception as e:
            logging.error(f"Error checking emails: {e}")

    def process_single_email(self, imap_server: imaplib.IMAP4, mail_id: bytes):
        """
        Process a single email message.
        
        Args:
            imap_server: Active IMAP connection
            mail_id: ID of the email to process
        """
        # Get UID
        status, uid_data = imap_server.fetch(mail_id, 'UID')
        if status != "OK":
            logging.error("Failed to fetch UID")
            return

        uid = uid_data[0].decode().split()[-1].replace(")", "")
        logging.info(f"Processing email with UID: {uid}")

        # Fetch email content
        status, msg_data = imap_server.fetch(mail_id, '(RFC822)')
        if status != "OK":
            logging.error("Failed to fetch email content")
            return

        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                body, attachments = self.extract_email_content(msg, uid)
                self.process_email(uid, msg["from"], msg["subject"], body, attachments)

    def process_email(self, uid: str, sender: str, subject: str, body: str, attachments: List[Dict[str, str]]):
        """
        Process email content and handle attachments.
        
        Args:
            uid: Email unique identifier
            sender: Email sender
            subject: Email subject
            body: Email body
            attachments: List of attachment metadata
        """
        logging.info("-----------------------------------------------")
        logging.info(f"From: {sender}")
        logging.info(f"Subject: {subject}")
        logging.info(f"Body: {body}")

        for attachment in attachments:
            if attachment["mimetype"] and attachment["mimetype"].startswith("image/"):
                seconds = 1
                logging.info(f"Processing image: {attachment['filename']}")
                self.show_image_onscreen(attachment["filepath"], seconds)
            else:
                logging.info(f"Attachment: {attachment['filename']} (Type: {attachment['mimetype']})")
            time.sleep(seconds)

    def show_image_onscreen(self, image_path: str, seconds: int = 1):
        """
        Display an image on screen using fbi.
        
        Args:
            image_path: Path to the image file
            seconds: Duration to display the image
        """
        try:
            command = ["sudo", "fbi", "-T", "1", "-a", "-t", str(seconds), image_path]
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to display image: {e}")

    def start(self, wait_interval: int = 30):
        """
        Start the email monitoring loop.
        
        Args:
            wait_interval: Time to wait between inbox checks (in seconds)
        """
        logging.info("Starting email monitoring...")
        while True:
            self.check_emails()
            time.sleep(wait_interval)
            logging.info("Checking inbox...")


if __name__ == "__main__":
    raio = Raio()
    raio.start()
