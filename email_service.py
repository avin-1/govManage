"""
email_service.py
────────────────
Modular, reusable SMTP email service for govManage.

Environment variables (all optional — service degrades gracefully if absent):
    SMTP_HOST        SMTP server hostname          (e.g. smtp.gmail.com)
    SMTP_PORT        Port number                   (default: 587)
    SMTP_USER        Login username / email address
    SMTP_PASSWORD    Login password / app password
    SMTP_FROM        "From" display address        (defaults to SMTP_USER)
    SMTP_USE_TLS     Use STARTTLS on port 587      (default: "true")
    SMTP_USE_SSL     Use SSL on port 465           (default: "false")
    EMAIL_RECIPIENTS Comma-separated default recipients

All functions return a dict: {"ok": bool, "message": str, ...}
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def get_smtp_config() -> Dict[str, Any]:
    """Return a dict with the current SMTP configuration from env vars."""
    return {
        "host": os.getenv("SMTP_HOST", "").strip(),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER", "").strip(),
        "password": os.getenv("SMTP_PASSWORD", "").strip(),
        "from_addr": os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "")).strip(),
        "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() not in ("false", "0", "no"),
        "use_ssl": os.getenv("SMTP_USE_SSL", "false").lower() in ("true", "1", "yes"),
    }


def is_configured() -> bool:
    """Return True only if the minimum required SMTP env vars are present."""
    cfg = get_smtp_config()
    return bool(cfg["host"] and cfg["user"] and cfg["password"])


def get_default_recipients() -> List[str]:
    """Parse EMAIL_RECIPIENTS env var into a list of addresses."""
    raw = os.getenv("EMAIL_RECIPIENTS", "").strip()
    if not raw:
        return []
    return [r.strip() for r in raw.split(",") if r.strip()]


# ---------------------------------------------------------------------------
# Core send
# ---------------------------------------------------------------------------

def send_email(
    to_addrs: List[str],
    subject: str,
    html_body: str,
    text_body: str = "",
    from_addr: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send a MIME multipart email via SMTP.

    Returns {"ok": True} on success or {"ok": False, "error": "<message>"} on failure.
    Raises no exceptions — all errors are captured and returned.
    """
    if not to_addrs:
        return {"ok": False, "error": "No recipients provided."}

    cfg = get_smtp_config()
    if not is_configured():
        return {
            "ok": False,
            "error": "SMTP not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in .env",
        }

    sender = from_addr or cfg["from_addr"] or cfg["user"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(to_addrs)

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        ctx = ssl.create_default_context()

        if cfg["use_ssl"]:
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=ctx) as server:
                server.login(cfg["user"], cfg["password"])
                server.sendmail(sender, to_addrs, msg.as_string())
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
                server.ehlo()
                if cfg["use_tls"]:
                    server.starttls(context=ctx)
                    server.ehlo()
                server.login(cfg["user"], cfg["password"])
                server.sendmail(sender, to_addrs, msg.as_string())

        logger.info("[email] Sent '%s' to %s", subject, to_addrs)
        return {"ok": True, "recipients": to_addrs, "subject": subject}

    except smtplib.SMTPAuthenticationError as exc:
        msg_str = "SMTP authentication failed. Check SMTP_USER / SMTP_PASSWORD."
        logger.error("[email] %s — %s", msg_str, exc)
        return {"ok": False, "error": msg_str}
    except smtplib.SMTPConnectError as exc:
        msg_str = f"Could not connect to {cfg['host']}:{cfg['port']}."
        logger.error("[email] %s — %s", msg_str, exc)
        return {"ok": False, "error": msg_str}
    except Exception as exc:
        logger.exception("[email] Unexpected send error")
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Weekly report data gathering
# ---------------------------------------------------------------------------

def compose_weekly_report_data() -> Dict[str, Any]:
    """
    Gather a snapshot of GRC metrics from the database.
    Import `db` lazily to avoid circular imports.
    """
    from database import db  # lazy import

    now = datetime.now(timezone.utc)

    # Policy packs
    packs = db.list_policy_packs()
    total_packs = len(packs)
    recent_packs = [
        p for p in packs
        if p.get("created_at", "") >= now.isoformat()[:7]  # same month
    ]

    # Frameworks
    frameworks = db.list_frameworks()

    # Risk library
    risks = db.list_risk_library()
    high_risks = [r for r in risks if r.get("severity") == "High"]
    medium_risks = [r for r in risks if r.get("severity") == "Medium"]
    low_risks = [r for r in risks if r.get("severity") == "Low"]

    # Policy documents
    docs = db.list_policy_documents()
    active_docs = [d for d in docs if d.get("is_active", True)]

    # Recent governance actions
    actions = list(db.actions_col.find({}, {"_id": 0}).sort("timestamp", -1).limit(20))
    approved = sum(1 for a in actions if a.get("status") == "Approved")
    flagged = sum(1 for a in actions if a.get("status") in ["Rejected", "Review", "Flagged"])

    # Latest compliance reports (from reports collection)
    reports = list(db.reports_col.find({}, {"_id": 0}).sort("generated_at", -1).limit(5))

    return {
        "generated_at": now.strftime("%B %d, %Y at %H:%M UTC"),
        "total_policy_packs": total_packs,
        "packs_this_month": len(recent_packs),
        "recent_packs": recent_packs[:5],
        "total_frameworks": len(frameworks),
        "framework_list": [f.get("name", "") for f in frameworks[:8]],
        "total_risks": len(risks),
        "high_risk_count": len(high_risks),
        "medium_risk_count": len(medium_risks),
        "low_risk_count": len(low_risks),
        "top_high_risks": [r.get("title", "") for r in high_risks[:5]],
        "active_documents": len(active_docs),
        "actions_reviewed": len(actions),
        "actions_approved": approved,
        "actions_flagged": flagged,
        "recent_reports": reports,
    }


# ---------------------------------------------------------------------------
# HTML email template
# ---------------------------------------------------------------------------

def build_weekly_report_html(data: Dict[str, Any]) -> str:
    """Render a professional HTML email from the report data dict."""

    fw_tags = "".join(
        f'<span style="background:#e0e7ff;color:#4338ca;padding:2px 8px;border-radius:12px;'
        f'font-size:11px;font-weight:600;margin:2px;display:inline-block">{fw}</span>'
        for fw in data.get("framework_list", [])
    )

    risk_rows = "".join(
        f'<tr><td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;font-size:13px;color:#1e293b">'
        f'⚠ {risk}</td></tr>'
        for risk in data.get("top_high_risks", [])
    ) or '<tr><td style="padding:8px 12px;color:#64748b;font-size:13px">No high-severity risks flagged.</td></tr>'

    recent_pack_rows = "".join(
        f'<tr><td style="padding:7px 12px;border-bottom:1px solid #f1f5f9;font-size:12px;color:#475569">'
        f'{p.get("policy", {}).get("name", p.get("pack_id", "—"))}</td>'
        f'<td style="padding:7px 12px;border-bottom:1px solid #f1f5f9;font-size:12px;color:#64748b">'
        f'{p.get("sector","—")}</td>'
        f'<td style="padding:7px 12px;border-bottom:1px solid #f1f5f9;font-size:12px">'
        f'<span style="background:{"#fef3c7" if p.get("risk_level") == "Medium" else "#fee2e2" if p.get("risk_level") == "High" else "#d1fae5"};'
        f'color:{"#92400e" if p.get("risk_level") == "Medium" else "#991b1b" if p.get("risk_level") == "High" else "#065f46"};'
        f'padding:2px 8px;border-radius:9px;font-weight:700;font-size:11px">{p.get("risk_level","—")}</span>'
        f'</td></tr>'
        for p in data.get("recent_packs", [])
    ) or '<tr><td colspan="3" style="padding:8px 12px;color:#64748b;font-size:13px">No policy packs generated this week.</td></tr>'

    compliance_score = max(0, min(100,
        100 - int(data.get("high_risk_count", 0) * 8) - int(data.get("actions_flagged", 0) * 3)
    ))
    score_color = "#10b981" if compliance_score >= 80 else "#f59e0b" if compliance_score >= 60 else "#ef4444"

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>govManage Weekly GRC Report</title></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 0">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%">

  <!-- Header -->
  <tr><td style="background:linear-gradient(135deg,#312e81 0%,#4338ca 60%,#1d4ed8 100%);
               border-radius:16px 16px 0 0;padding:36px 40px 28px">
    <table width="100%"><tr>
      <td>
        <div style="background:rgba(255,255,255,0.12);display:inline-block;padding:8px 14px;
                    border-radius:8px;margin-bottom:14px">
          <span style="color:#a5b4fc;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase">
            GRC Intelligence
          </span>
        </div>
        <h1 style="margin:0 0 6px;color:#ffffff;font-size:26px;font-weight:800;line-height:1.2">
          Weekly GRC Summary
        </h1>
        <p style="margin:0;color:#c7d2fe;font-size:14px">{data.get("generated_at","")}</p>
      </td>
      <td align="right" valign="top">
        <div style="background:rgba(255,255,255,0.1);border:2px solid rgba(255,255,255,0.2);
                    border-radius:50%;width:72px;height:72px;display:flex;align-items:center;
                    justify-content:center;text-align:center;line-height:72px;
                    font-size:28px">🛡</div>
      </td>
    </tr></table>
  </td></tr>

  <!-- KPI strip -->
  <tr><td style="background:#ffffff;padding:24px 40px 20px;border-bottom:1px solid #e2e8f0">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td align="center" style="width:25%">
        <div style="font-size:28px;font-weight:800;color:#4338ca">{data.get("total_policy_packs",0)}</div>
        <div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.5px">Policy Packs</div>
      </td>
      <td align="center" style="width:25%">
        <div style="font-size:28px;font-weight:800;color:#10b981">{data.get("total_frameworks",0)}</div>
        <div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.5px">Frameworks</div>
      </td>
      <td align="center" style="width:25%">
        <div style="font-size:28px;font-weight:800;color:#ef4444">{data.get("high_risk_count",0)}</div>
        <div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.5px">High Risks</div>
      </td>
      <td align="center" style="width:25%">
        <div style="font-size:28px;font-weight:800;color:{score_color}">{compliance_score}%</div>
        <div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.5px">Compliance Score</div>
      </td>
    </tr></table>
  </td></tr>

  <!-- Compliance score bar -->
  <tr><td style="background:#ffffff;padding:0 40px 24px">
    <div style="background:#f1f5f9;border-radius:8px;height:8px;overflow:hidden">
      <div style="background:{score_color};width:{compliance_score}%;height:8px;border-radius:8px;
                  transition:width 0.5s"></div>
    </div>
    <p style="margin:8px 0 0;font-size:12px;color:#94a3b8;text-align:right">
      Compliance readiness: <strong style="color:{score_color}">{compliance_score}%</strong>
    </p>
  </td></tr>

  <!-- Risk summary -->
  <tr><td style="background:#ffffff;padding:0 40px 28px">
    <h2 style="margin:0 0 14px;font-size:16px;font-weight:700;color:#1e293b;
               border-left:4px solid #ef4444;padding-left:10px">
      ⚠ High-Priority Risk Factors
    </h2>
    <table width="100%" style="border-radius:10px;overflow:hidden;border:1px solid #fee2e2">
      {risk_rows}
    </table>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px"><tr>
      <td align="center" style="background:#fef3c7;border-radius:8px;padding:10px">
        <span style="font-size:12px;font-weight:700;color:#92400e">Medium: {data.get("medium_risk_count",0)}</span>
      </td>
      <td width="12"></td>
      <td align="center" style="background:#d1fae5;border-radius:8px;padding:10px">
        <span style="font-size:12px;font-weight:700;color:#065f46">Low: {data.get("low_risk_count",0)}</span>
      </td>
      <td width="12"></td>
      <td align="center" style="background:#f0fdf4;border-radius:8px;padding:10px">
        <span style="font-size:12px;font-weight:700;color:#166534">Total: {data.get("total_risks",0)}</span>
      </td>
    </tr></table>
  </td></tr>

  <!-- Divider -->
  <tr><td style="background:#ffffff;padding:0 40px"><hr style="border:none;border-top:1px solid #e2e8f0;margin:0"></td></tr>

  <!-- Recent policy packs -->
  <tr><td style="background:#ffffff;padding:24px 40px 28px">
    <h2 style="margin:0 0 14px;font-size:16px;font-weight:700;color:#1e293b;
               border-left:4px solid #4338ca;padding-left:10px">
      📋 Recent Policy Packs
    </h2>
    <table width="100%" style="border-radius:10px;overflow:hidden;border:1px solid #e2e8f0">
      <tr style="background:#f8fafc">
        <th style="text-align:left;padding:8px 12px;font-size:12px;font-weight:700;color:#475569;
                   text-transform:uppercase;letter-spacing:0.5px">Policy Name</th>
        <th style="text-align:left;padding:8px 12px;font-size:12px;font-weight:700;color:#475569;
                   text-transform:uppercase;letter-spacing:0.5px">Sector</th>
        <th style="text-align:left;padding:8px 12px;font-size:12px;font-weight:700;color:#475569;
                   text-transform:uppercase;letter-spacing:0.5px">Risk Level</th>
      </tr>
      {recent_pack_rows}
    </table>
  </td></tr>

  <!-- Frameworks in use -->
  <tr><td style="background:#ffffff;padding:0 40px 28px">
    <h2 style="margin:0 0 14px;font-size:16px;font-weight:700;color:#1e293b;
               border-left:4px solid #10b981;padding-left:10px">
      🔒 Active Compliance Frameworks
    </h2>
    <div>{fw_tags}</div>
  </td></tr>

  <!-- Governance actions -->
  <tr><td style="background:#ffffff;padding:0 40px 28px">
    <h2 style="margin:0 0 14px;font-size:16px;font-weight:700;color:#1e293b;
               border-left:4px solid #f59e0b;padding-left:10px">
      📊 Governance Activity (Last 20 Actions)
    </h2>
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td align="center" style="background:#f0fdf4;border-radius:10px;padding:16px">
        <div style="font-size:24px;font-weight:800;color:#16a34a">{data.get("actions_approved",0)}</div>
        <div style="font-size:11px;font-weight:700;color:#166534;text-transform:uppercase">Approved</div>
      </td>
      <td width="14"></td>
      <td align="center" style="background:#fef2f2;border-radius:10px;padding:16px">
        <div style="font-size:24px;font-weight:800;color:#dc2626">{data.get("actions_flagged",0)}</div>
        <div style="font-size:11px;font-weight:700;color:#991b1b;text-transform:uppercase">Flagged / Review</div>
      </td>
      <td width="14"></td>
      <td align="center" style="background:#f8fafc;border-radius:10px;padding:16px">
        <div style="font-size:24px;font-weight:800;color:#334155">{data.get("active_documents",0)}</div>
        <div style="font-size:11px;font-weight:700;color:#475569;text-transform:uppercase">Active Docs</div>
      </td>
    </tr></table>
  </td></tr>

  <!-- Recommendations -->
  <tr><td style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:0;padding:20px 40px">
    <h2 style="margin:0 0 10px;font-size:14px;font-weight:700;color:#1e40af">💡 Automated Recommendations</h2>
    <ul style="margin:0;padding-left:18px;color:#1d4ed8;font-size:13px;line-height:1.7">
      {"<li>Review and remediate <strong>" + str(data.get("high_risk_count",0)) + " high-severity risk factors</strong> immediately.</li>" if data.get("high_risk_count",0) > 0 else "<li>No high-severity risks detected. Maintain current controls.</li>"}
      {"<li><strong>" + str(data.get("actions_flagged",0)) + " governance actions</strong> require manual review and resolution.</li>" if data.get("actions_flagged",0) > 0 else ""}
      {"<li>Compliance readiness is <strong>below 60%</strong> — initiate a policy gap analysis.</li>" if compliance_score < 60 else "<li>Compliance readiness is healthy at <strong>" + str(compliance_score) + "%</strong>.</li>"}
      <li>Ensure all active policy packs are reviewed quarterly.</li>
    </ul>
  </td></tr>

  <!-- Footer -->
  <tr><td style="background:#1e293b;border-radius:0 0 16px 16px;padding:20px 40px">
    <p style="margin:0;font-size:11px;color:#94a3b8;text-align:center">
      This report was automatically generated by <strong style="color:#c7d2fe">govManage Intelligence</strong>.
      &nbsp;|&nbsp; Do not reply to this email.
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def build_weekly_report_text(data: Dict[str, Any]) -> str:
    """Plain-text fallback for the weekly report email."""
    lines = [
        "govManage — Weekly GRC Summary",
        "=" * 40,
        f"Generated: {data.get('generated_at', '')}",
        "",
        "OVERVIEW",
        f"  Policy Packs:      {data.get('total_policy_packs', 0)}",
        f"  Frameworks Active: {data.get('total_frameworks', 0)}",
        f"  High Risks:        {data.get('high_risk_count', 0)}",
        f"  Medium Risks:      {data.get('medium_risk_count', 0)}",
        f"  Low Risks:         {data.get('low_risk_count', 0)}",
        "",
        "HIGH-PRIORITY RISKS",
    ]
    for r in data.get("top_high_risks", []):
        lines.append(f"  ⚠ {r}")
    lines += [
        "",
        "GOVERNANCE ACTIVITY (last 20 actions)",
        f"  Approved: {data.get('actions_approved', 0)}",
        f"  Flagged:  {data.get('actions_flagged', 0)}",
        "",
        "ACTIVE COMPLIANCE FRAMEWORKS",
        "  " + ", ".join(data.get("framework_list", [])),
        "",
        "─" * 40,
        "Automated report from govManage. Do not reply.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orchestrated send
# ---------------------------------------------------------------------------

def send_weekly_report(
    recipients: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Compose and dispatch the weekly GRC report email.

    recipients: list of email addresses; falls back to EMAIL_RECIPIENTS env var.
    Returns the result dict from send_email().
    """
    if recipients is None:
        recipients = get_default_recipients()

    if not recipients:
        return {"ok": False, "error": "No recipients configured. Set EMAIL_RECIPIENTS in .env"}

    try:
        data = compose_weekly_report_data()
    except Exception as exc:
        logger.exception("[email] Failed to compose report data")
        return {"ok": False, "error": f"Data gathering failed: {exc}"}

    subject = f"govManage Weekly GRC Report — {data.get('generated_at', 'Weekly')}"
    html_body = build_weekly_report_html(data)
    text_body = build_weekly_report_text(data)

    result = send_email(recipients, subject, html_body, text_body)
    result["report_data"] = {
        k: v for k, v in data.items()
        if k not in ("recent_packs", "recent_reports")  # keep response small
    }
    return result
