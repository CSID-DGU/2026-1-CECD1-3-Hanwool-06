from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import load_dotenv


BASE = "https://i121.seoul.go.kr"
LOGIN_FORM_URL = f"{BASE}/cs/cyber/front/login/NR_loginForm.do"
LOGIN_ACTION_URL = f"{BASE}/cs/cyber/front/login/AR_loginAction.do"
MYARISU_URL = f"{BASE}/cs/cyber/front/mypage/NR_myArisu.do"


class LoginError(RuntimeError):
    pass


def _new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        }
    )
    return s


def login(user_id: str, user_pwd: str, *, timeout: float = 30.0) -> requests.Session:
    """Perform form login and return an authenticated session.

    Raises LoginError if the session cannot reach the protected mypage.
    """
    if not user_id or not user_pwd:
        raise LoginError("user_id and user_pwd must be non-empty")

    session = _new_session()

    # Prime cookies on the login form
    r = session.get(LOGIN_FORM_URL, params={"_m": "m7"}, timeout=timeout)
    r.raise_for_status()

    # Submit credentials
    r = session.post(
        LOGIN_ACTION_URL,
        data={"userId": user_id, "userPwd": user_pwd},
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": f"{LOGIN_FORM_URL}?_m=m7",
            "Origin": BASE,
            "Accept": "*/*",
        },
        timeout=timeout,
    )
    r.raise_for_status()
    login_body = r.text.strip()

    # Verify by hitting a member-only page
    verify = session.get(MYARISU_URL, params={"_m": "m6"}, timeout=timeout)
    verify.raise_for_status()
    if _looks_like_login_page(verify.text) or "NR_loginForm.do" in verify.url:
        raise LoginError(
            f"login appears to have failed; "
            f"login_action_body={login_body!r}; verify_url={verify.url!r}"
        )
    return session


def _looks_like_login_page(html: str) -> bool:
    markers = ("name=\"userId\"", "name=\"userPwd\"", "로그인이 필요")
    return any(m in html for m in markers)


def session_from_env(env_path: Path | str | None = None) -> requests.Session:
    """Load I121_USER_ID / I121_USER_PWD from .env and log in."""
    if env_path is not None:
        load_dotenv(dotenv_path=env_path, override=True)
    else:
        load_dotenv(override=False)
    user_id = os.environ.get("I121_USER_ID", "").strip()
    user_pwd = os.environ.get("I121_USER_PWD", "").strip()
    if not user_id or not user_pwd:
        raise LoginError(
            "missing credentials; copy .env.example to .env and set "
            "I121_USER_ID / I121_USER_PWD"
        )
    return login(user_id, user_pwd)
