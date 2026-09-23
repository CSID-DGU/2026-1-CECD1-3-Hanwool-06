import { useState } from "react";
import { request } from "../api.js";

// Check session first, then let the browser handle the authenticated file URL.
export default function FileLink({ href, filename, preview = false, children, className = "secondary-button" }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function open(event) {
    if (event.metaKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    if (busy) return;
    const tab = preview ? window.open("", "_blank") : null;
    if (tab) tab.opener = null;
    setBusy(true); setError("");
    try {
      await request("/auth/me");
      if (preview && tab) tab.location.href = href;
      else {
        const link = document.createElement("a");
        link.href = href;
        if (preview) { link.target = "_blank"; link.rel = "noreferrer"; }
        else link.download = filename;
        document.body.append(link); link.click(); link.remove();
      }
    } catch (e) { tab?.close(); setError(e.message); }
    finally { setBusy(false); }
  }
  return <span className="file-action"><a className={className} href={href} download={preview ? undefined : filename} onClick={open} aria-disabled={busy} target={preview ? "_blank" : undefined} rel={preview ? "noreferrer" : undefined}>{busy ? "문서 준비 중…" : children}</a>{error && <span className="file-error" role="alert">{error}</span>}</span>;
}
