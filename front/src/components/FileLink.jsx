import { useState } from "react";
import { isStatic, request } from "../api.js";

// 요청에 붙인 표식을 서버가 응답 쿠키로 돌려주면 파일 준비가 끝난 것이다. 그때까지 안내를 띄운다.
function waitForCookie(name, timeoutMs) {
  return new Promise((resolve) => {
    const started = Date.now();
    const timer = setInterval(() => {
      if (document.cookie.split("; ").some((c) => c.startsWith(`${name}=`)) || Date.now() - started > timeoutMs) {
        clearInterval(timer);
        document.cookie = `${name}=; Max-Age=0; path=/`;
        resolve();
      }
    }, 300);
  });
}

// Check session first, then let the browser handle the authenticated file URL.
export default function FileLink({ href, filename, preview = false, children, className = "secondary-button" }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function open(event) {
    if (event.metaKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    if (busy) return;
    if (isStatic) { setError("저장된 화면에서는 내려받을 수 없습니다."); return; }
    const tab = preview ? window.open("", "_blank") : null;
    if (tab) tab.opener = null;
    setBusy(true); setError("");
    const token = Math.random().toString(36).slice(2, 12);
    const url = `${href}${href.includes("?") ? "&" : "?"}dl=${token}`;
    try {
      await request("/auth/me");
      if (preview && tab) tab.location.href = url;
      else {
        const link = document.createElement("a");
        link.href = url;
        if (preview) { link.target = "_blank"; link.rel = "noreferrer"; }
        else link.download = filename;
        document.body.append(link); link.click(); link.remove();
      }
      await waitForCookie(`dl_${token}`, 180_000);
    } catch (e) { tab?.close(); setError(e.message); }
    finally { setBusy(false); }
  }
  return <span className="file-action">
    <a className={className} href={href} download={preview ? undefined : filename} onClick={open} aria-disabled={busy} target={preview ? "_blank" : undefined} rel={preview ? "noreferrer" : undefined}>{busy ? "문서 준비 중…" : children}</a>
    {error && <span className="file-error" role="alert">{error}</span>}
    {busy && <div className="download-notice" role="status" aria-live="polite"><div>
      <span className="spinner" aria-hidden="true" />
      {preview ? "문서를 만들고 있습니다." : "파일을 만들고 있습니다."}
      <small>자료가 많으면 몇십 초 걸릴 수 있습니다. 다 되면 {preview ? "새 탭에 열립니다." : "브라우저가 저장합니다."}</small>
    </div></div>}
  </span>;
}
