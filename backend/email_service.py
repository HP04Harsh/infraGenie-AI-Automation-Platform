"""Email sending via SMTP with portal-stored credentials."""
import logging
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


async def _get_smtp_config(db, user_id: str) -> Optional[Dict[str, Any]]:
    conn = await db.integrations.find_one({"user_id": user_id, "key": "smtp"})
    secret = await db.integration_secrets.find_one({"user_id": user_id, "key": "smtp"})
    if not (conn and conn.get("connected") and secret):
        return None
    fields = conn.get("fields") or {}
    return {
        "host": fields.get("host", ""),
        "port": int(fields.get("port", 587)),
        "username": fields.get("username", ""),
        "password": secret.get("password", ""),
        "from_email": fields.get("from_email", fields.get("username", "")),
        "use_tls": fields.get("use_tls", True),
    }


async def send_email(
    db, user_id: str,
    to: str,
    subject: str,
    html_body: str,
    text_body: str = "",
) -> bool:
    cfg = await _get_smtp_config(db, user_id)
    if not cfg:
        logger.warning("SMTP not configured, cannot send email to %s", to)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["from_email"]
    msg["To"] = to
    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    def _send():
        try:
            server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=15)
            if cfg["use_tls"]:
                server.starttls()
            if cfg["username"] and cfg["password"]:
                server.login(cfg["username"], cfg["password"])
            server.sendmail(cfg["from_email"], [to], msg.as_string())
            server.quit()
            return True
        except Exception as e:
            logger.error("SMTP send failed: %s", e)
            return False

    return await asyncio.to_thread(_send)


def build_alert_email_body(
    vm_name: str,
    issue_type: str,
    details: str,
    ticket_number: str,
    apply_link: str = "",
) -> str:
    """Build a styled HTML email for monitoring alerts."""
    severity_colors = {
        "cpu": "#e74c3c",
        "memory": "#e67e22",
        "disk": "#f39c12",
        "shutdown": "#c0392b",
        "health": "#e74c3c",
    }
    color = severity_colors.get(issue_type, "#e74c3c")
    issue_labels = {
        "cpu": "High CPU Usage",
        "memory": "High Memory Usage",
        "disk": "High Disk Usage",
        "shutdown": "VM Shutdown Detected",
        "health": "VM Health Issue",
    }
    label = issue_labels.get(issue_type, issue_type.title())

    apply_html = ""
    if apply_link:
        apply_html = f"""
        <tr>
            <td style="padding: 15px; text-align: center;">
                <a href="{apply_link}" style="display: inline-block; padding: 12px 30px; background-color: #3498db; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    Apply Auto-Fix Script
                </a>
            </td>
        </tr>
        <tr>
            <td style="padding: 0 15px 15px; text-align: center; font-size: 12px; color: #888;">
                This script is AI-generated and may not fully resolve the issue. It is a temporary solution.
                Once applied, please verify the VM status manually.
            </td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f4f4;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding: 20px;">
<table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
<tr><td style="background-color: {color}; padding: 20px; text-align: center;">
<h1 style="color: white; margin: 0; font-size: 22px;">InfraGenie Alert</h1>
</td></tr>
<tr><td style="padding: 20px;">
<h2 style="color: #333; margin-top: 0;">{label}</h2>
<table width="100%" cellpadding="8">
<tr><td style="font-weight: bold; color: #555; width: 120px;">Virtual Machine:</td><td style="color: #333;">{vm_name}</td></tr>
<tr><td style="font-weight: bold; color: #555;">Issue:</td><td style="color: #333;">{details}</td></tr>
<tr><td style="font-weight: bold; color: #555;">Ticket:</td><td style="color: #333;">{ticket_number}</td></tr>
<tr><td style="font-weight: bold; color: #555;">Reported At:</td><td style="color: #333;">{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M UTC')}</td></tr>
</table>
</td></tr>
{apply_html}
<tr><td style="background-color: #f9f9f9; padding: 15px; text-align: center; font-size: 12px; color: #999;">
InfraGenie AI Automation Platform &mdash; This is an automated alert.
</td></tr>
</table></td></tr></table></body>
</html>"""


def build_resolution_email_body(vm_name: str, ticket_number: str, script_summary: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f4f4;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding: 20px;">
<table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
<tr><td style="background-color: #27ae60; padding: 20px; text-align: center;">
<h1 style="color: white; margin: 0; font-size: 22px;">Issue Resolved</h1>
</td></tr>
<tr><td style="padding: 20px;">
<h2 style="color: #333; margin-top: 0;">Auto-Fix Applied Successfully</h2>
<table width="100%" cellpadding="8">
<tr><td style="font-weight: bold; color: #555; width: 120px;">Virtual Machine:</td><td style="color: #333;">{vm_name}</td></tr>
<tr><td style="font-weight: bold; color: #555;">Ticket:</td><td style="color: #333;">{ticket_number}</td></tr>
<tr><td style="font-weight: bold; color: #555;">Script Applied:</td><td style="color: #333;">{script_summary}</td></tr>
</table>
<p style="color: #555; line-height: 1.5;">The AI-generated fix script has been executed on your VM. This is a temporary solution. Please log in and verify the VM status manually.</p>
</td></tr>
<tr><td style="background-color: #f9f9f9; padding: 15px; text-align: center; font-size: 12px; color: #999;">
InfraGenie AI Automation Platform &mdash; Automated resolution report.
</td></tr>
</table></td></tr></table></body>
</html>"""
