"""Gmail SMTP 발송. 앱 비밀번호(SMTP_PASS)를 .env 에 둔다."""
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

from . import config


def send_mail(subject: str, body_html: str, to: str | None = None) -> dict:
    to = (to or config.ALERT_TO).strip()
    if not config.smtp_ready():
        return {"sent": False, "reason": "SMTP_USER/SMTP_PASS 미설정 (.env 확인)"}
    if not to:
        return {"sent": False, "reason": "수신처(ALERT_TO 또는 to)가 없습니다."}

    msg = MIMEText(body_html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr(("물샘이 · 상수도 이상징후 관제", config.ALERT_FROM))
    msg["To"] = to
    recipients = [a.strip() for a in to.split(",") if a.strip()]

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as s:
        s.starttls()
        s.login(config.SMTP_USER, config.SMTP_PASS)
        s.sendmail(config.ALERT_FROM, recipients, msg.as_string())
    return {"sent": True, "to": recipients}


def build_alert_html(item: dict, analysis: dict | None = None) -> str:
    """이상 1건 + (선택)원인분석을 메일 본문 HTML 로."""
    sev = item.get("심각도", "")
    color = "#d92d20" if sev == "경고" else "#dc8a00" if sev == "주의" else "#0e7c7b"
    rows = "".join(
        f"<tr><th align='left' style='padding:4px 12px 4px 0;color:#667;'>{k}</th>"
        f"<td style='padding:4px 0;'>{v}</td></tr>"
        for k, v in [
            ("역명", item.get("역명")),
            ("영업사업소", item.get("영업사업소") or "-"),
            ("기준일", item.get("날짜")),
            ("심각도", f"<b style='color:{color}'>{sev}</b>"),
            ("예측 / 실제", f"{item.get('predicted_ton')}톤 / {item.get('actual_ton')}톤"),
            ("예측오차", f"{item.get('error_ton')}톤 ({item.get('pct')}%, {item.get('방향')})"),
            ("deviation", item.get("deviation_score")),
        ]
    )
    cause = ""
    if analysis and not analysis.get("error"):
        a = analysis.get("analysis", {})
        ev = "".join(
            f"<li>{e.get('title','')} "
            f"<span style='color:#889'>{e.get('date','')}</span> "
            f"{('· ' + e['source']) if e.get('source') else ''}</li>"
            for e in (a.get("events") or [])
        )
        cause = (
            "<h3 style='margin:18px 0 6px'>원인 분석(에이전트)</h3>"
            f"<p style='margin:4px 0'><b>{a.get('primary_cause','')}</b> "
            f"<span style='color:#889'>(확신도: {a.get('confidence','')})</span></p>"
            f"<ul style='margin:4px 0 0'>{''.join(f'<li>{r}</li>' for r in (a.get('reasons') or []))}</ul>"
            + (f"<p style='margin:8px 0 2px;color:#667'>관련 정보</p><ul>{ev}</ul>" if ev else "")
            + (f"<p style='margin:8px 0 0'>권장 조치: {a.get('recommendation','')}</p>" if a.get('recommendation') else "")
        )

    return (
        "<div style='font-family:Pretendard,Apple SD Gothic Neo,sans-serif;max-width:560px'>"
        f"<h2 style='color:{color};margin:0 0 4px'>[{sev}] {item.get('역명')} 상수도 이상징후</h2>"
        f"<p style='color:#667;margin:0 0 12px'>{item.get('날짜')} 기준 자동 알림</p>"
        f"<table style='font-size:14px'>{rows}</table>"
        f"{cause}"
        "<p style='margin-top:20px;color:#99a;font-size:12px'>"
        "본 메일은 상수도 이상징후 관제 에이전트 '물샘이'가 자동 발송했습니다.</p>"
        "</div>"
    )
