import imaplib
import email
import time
from datetime import datetime
import ssl
import os
import mimetypes
import configparser
import subprocess

class Raio:

    def __init__(self):
        print("Raio started:::")
        self.config = self.load_config()

    def load_config(self):
        config = configparser.ConfigParser()
        config_file = "config.ini"

        if not os.path.exists(config_file):
            print("Configuration file not found. Let's set it up.")
            # Prompt user for SMTP/IMAP settings
            config["IMAP"] = {
                "server": input("Enter IMAP server (e.g., imap.example.com): ").strip(),
                "port": input("Enter IMAP port (default 143): ").strip() or "143",
                "email": input("Enter your email address: ").strip(),
                "password": input("Enter your email password: ").strip()
            }
            # Save to config file
            with open(config_file, "w") as file:
                config.write(file)
            print(f"Configuration saved to {config_file}")
        else:
            # Load existing config
            config.read(config_file)

        return config

    def check_emails(self):
        try:
            # Load IMAP settings from config
            imap_server_address = self.config["IMAP"]["server"]
            imap_port = int(self.config["IMAP"]["port"])
            email_address = self.config["IMAP"]["email"]
            email_password = self.config["IMAP"]["password"]

            # Connect to the IMAP server
            imap_server = imaplib.IMAP4(imap_server_address, imap_port)

            # Disable certificate verification (not recommended for production)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            # Upgrade the connection to TLS using STARTTLS
            # imap_server.starttls(ssl_context=ssl_context)

            # Log in to the server
            imap_server.login(email_address, email_password)
            imap_server.select('INBOX')

            # Search for unseen emails
            #status, messages = imap_server.search(None, 'UNSEEN')
            status, messages = imap_server.search(None, 'ALL')

            for mail_id in messages[0].split():
                status, uid_data = imap_server.fetch(mail_id, 'UID')
                if status == "OK":
                    uid = uid_data[0].decode().split()[-1].replace(")", "")  # Extract the UID
                    print(f"Processing email with UID: {uid}")

                status, msg_data = imap_server.fetch(mail_id, '(RFC822)')
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject = msg['subject']
                        sender = msg["from"]
                        body = ""
                        attachments = []

                        # Handle multipart emails
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))

                                # Get the email body
                                if content_type == "text/plain" and "attachment" not in content_disposition:
                                    body = part.get_payload(decode=True)
                                    if body:
                                        body = body.decode()

                                # Check for attachments
                                if "attachment" in content_disposition or part.get_filename():
                                    filename = "mail" + uid + "_" + part.get_filename()
                                    if filename:
                                        # Save the attachment
                                        filepath = os.path.join("attachments", filename)
                                        os.makedirs("attachments", exist_ok=True)
                                        with open(filepath, "wb") as f:
                                            f.write(part.get_payload(decode=True))
                                        attachments.append({"filename": filename, "filepath": filepath, "mimetype": mimetypes.guess_type(filepath)[0]})
                        else:
                            # Handle non-multipart emails
                            body = msg.get_payload(decode=True)
                            if body:
                                body = body.decode()

                        # Perform actions with subject, body, and attachments
                        self.process_email(uid, sender, subject, body, attachments)

            # Close the connection
            imap_server.close()
            imap_server.logout()

        except Exception as e:
            print(f"[{datetime.now()}] Error: {e}")

    def process_email(self, uid, sender, subject, body, attachments):
        print("-----------------------------------------------")
        print("From:", sender)
        print("Subject:", subject)
        print("Body:", body)
        for a in attachments:
            if a["mimetype"] and a["mimetype"].startswith("image/"):
                # It's an image
                seconds=1
                print(f"Got image {a['filename']}")
                self.showimage_onscreen(a["filepath"],seconds)
                
            else:
                print(f"Got attachment {a['filename']} of type {a['mimetype']}")
            time.sleep(seconds)
    def showimage_onscreen(self,imguri,seconds=1):
        # Path to your image
        image_path = imguri
    
        # Construct the command
        command = ["sudo", "fbi", "-T", "1", "-a", "-t", str(seconds), image_path]

        # Run the command
        subprocess.run(command)
        

    def start(self, wait=30):
        # Continuous listening loop
        while True:
            self.check_emails()
            time.sleep(wait)  # in seconds
            print(":::::::::::::: CHECK INBOX ::::::::::::::::")


if __name__ == "__main__":
    raio = Raio()
    raio.start()
