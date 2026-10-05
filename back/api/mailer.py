"""Explicit user-triggered alerts to assigned office managers only."""
import smtplib
import ssl
from email.mime.text import MIMEText
from email.utils import formataddr
from html import escape
from . import config


def send_mail(subject, body_html, to=None):
    if not config.smtp_ready():
        return {'sent': False, 'reason': '서버에 메일(SMTP) 설정이 없어 보내지 못했습니다.'}
    recipients = [a.strip() for a in (to or '').split(',') if a.strip()]
    if not recipients:
        return {'sent': False, 'reason': '이 사업소에는 메일을 받을 담당자가 없습니다.'}
    msg = MIMEText(body_html, 'html', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = formataddr(('물샘이 (상수도 이상징후 관제)', config.ALERT_FROM))
    msg['To'] = ', '.join(recipients)
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(config.SMTP_USER, config.SMTP_PASS)
            refused = smtp.sendmail(config.ALERT_FROM, recipients, msg.as_string())
        return {'sent': not refused, 'to': [r for r in recipients if r not in refused],
                **({'reason': '일부 담당자에게는 보내지 못했습니다.'} if refused else {})}
    except (smtplib.SMTPException, OSError):
        return {'sent': False, 'reason': '메일을 보내지 못했습니다. 서버의 메일 설정을 확인하세요.'}


def build_alert_html(item):
    def safe(value):
        return escape(str(value if value is not None else '미확인'))
    rows = ''.join(f'<tr><th>{safe(k)}</th><td>{safe(v)}</td></tr>' for k, v in [
        ('역명', item.get('역명')), ('사업소', item.get('영업사업소')), ('고객번호', item.get('고객번호')),
        ('기준일', item.get('날짜')), ('심각도', item.get('심각도')), ('실제 사용량(톤)', item.get('actual_ton')),
        ('예측 사용량(톤)', item.get('predicted_ton')), ('예측 대비(%)', item.get('pct'))])
    return f'<html><body><h2>상수도 이상징후 확인 요청</h2><table>{rows}</table><p>관제 화면에서 담당자가 보낸 알림입니다. 원인은 현장에서 확인해야 합니다.</p></body></html>'
