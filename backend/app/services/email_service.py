"""
Email Service — Outlook SMTP integration.

Sends real emails via smtp.office365.com using STARTTLS.
"""

import smtplib
import logging
from email.message import EmailMessage
from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_welcome_email(
    to_email: str,
    full_name: str,
    role: str,
    department: str,
    joining_date: str,
    work_location: str,
) -> EmailMessage:
    """Build the welcome invitation email with dynamic content."""

    subject = "Welcome to Reknew Orbit"

    # Plain text body
    text_body = f"""Hi {full_name},

Welcome to Reknew Orbit.

Your employee account has been created successfully.

Employee Details:
Role: {role}
Department: {department}
Joining Date: {joining_date}
Work Location: {work_location}

Please sign in and complete your onboarding tasks.

Regards,
ReKnew Team
"""

    # HTML body (styled with Reknew Orbit olive theme)
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#F7F6F2; font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#F7F6F2; padding:40px 20px;">
    <tr>
      <td align="center">
        <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="background-color:#FEFEFC; border:1px solid #E5E7EB; border-radius:16px; overflow:hidden;">

          <!-- Header -->
          <tr>
            <td style="background-color:#66785F; padding:32px 40px; text-align:center;">
              <h1 style="margin:0; color:#ffffff; font-size:22px; font-weight:700; letter-spacing:-0.02em;">
                Reknew <span style="color:#c2ceab;">Orbit</span>
              </h1>
              <p style="margin:8px 0 0; color:rgba(255,255,255,0.7); font-size:13px;">
                Employee Management System
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:36px 40px;">
              <h2 style="margin:0 0 6px; color:#2F3437; font-size:20px; font-weight:700;">
                Welcome aboard! 👋
              </h2>
              <p style="margin:0 0 24px; color:#6B7280; font-size:15px; line-height:1.6;">
                Hi <strong style="color:#2F3437;">{full_name}</strong>, your employee account has been created successfully.
              </p>

              <!-- Details Card -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#F7F6F2; border:1px solid #E5E7EB; border-radius:12px;">
                <tr>
                  <td style="padding:24px 28px;">
                    <p style="margin:0 0 16px; color:#6B7280; font-size:11px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase;">
                      Employee Details
                    </p>
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="padding:6px 0; color:#6B7280; font-size:14px; width:120px;">Role</td>
                        <td style="padding:6px 0; color:#2F3437; font-size:14px; font-weight:600;">{role}</td>
                      </tr>
                      <tr>
                        <td style="padding:6px 0; color:#6B7280; font-size:14px;">Department</td>
                        <td style="padding:6px 0; color:#2F3437; font-size:14px; font-weight:600;">{department}</td>
                      </tr>
                      <tr>
                        <td style="padding:6px 0; color:#6B7280; font-size:14px;">Joining Date</td>
                        <td style="padding:6px 0; color:#2F3437; font-size:14px; font-weight:600;">{joining_date}</td>
                      </tr>
                      <tr>
                        <td style="padding:6px 0; color:#6B7280; font-size:14px;">Location</td>
                        <td style="padding:6px 0; color:#2F3437; font-size:14px; font-weight:600;">{work_location}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- CTA -->
              <p style="margin:28px 0 0; color:#6B7280; font-size:14px; line-height:1.6;">
                Please sign in and complete your onboarding tasks.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:20px 40px; border-top:1px solid #E5E7EB; text-align:center;">
              <p style="margin:0; color:#9CA3AF; font-size:12px;">
                © 2026 ReKnew · Reknew Orbit Employee Management
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    return msg


def send_welcome_email(
    to_email: str,
    full_name: str,
    role: str,
    department: str,
    joining_date: str,
    work_location: str,
) -> bool:
    """
    Send welcome invitation email via Outlook SMTP.

    Returns True if email was sent successfully, False otherwise.
    """

    # Validate SMTP credentials are configured
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.error("SMTP credentials not configured. Set SMTP_USER and SMTP_PASSWORD in .env")
        return False

    try:
        # Build email
        msg = _build_welcome_email(
            to_email=to_email,
            full_name=full_name,
            role=role,
            department=department,
            joining_date=joining_date,
            work_location=work_location,
        )

        # Send via Outlook SMTP
        logger.info(f"Connecting to {settings.SMTP_HOST}:{settings.SMTP_PORT}...")

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(f"Welcome email sent successfully to {to_email}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        return False

    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending email to {to_email}: {e}")
        return False

    except Exception as e:
        logger.error(f"Unexpected error sending email to {to_email}: {e}")
        return False
