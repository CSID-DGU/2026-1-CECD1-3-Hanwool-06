import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

// 브라우저 기본 <select> 대신 쓰는 드롭다운. 펼친 목록의 여백·글꼴·색을 우리 스타일로 그린다.
// 목록은 문서 맨 위(body)에 띄우므로 스크롤 상자(표 머리글 등) 안에서도 잘리지 않는다.
// options: [{ value, label }]  value: 현재 값  onChange(value)  display: 버튼에 보일 글자(없으면 고른 선택지의 label)
// buttonClassName: 버튼 모양은 쓰는 곳이 정한다(머리글은 th-dropdown).  active: 강조 표시 여부
// anchor: "button"(기본)이면 버튼 아래에, "parent"면 버튼을 감싼 칸(표 머리글 칸 등)의 왼쪽 끝·폭에 맞춰 목록을 띄운다
export default function Dropdown({ options, value, onChange, display, label, buttonClassName = "", active = false, align = "left", anchor = "button" }) {
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const [position, setPosition] = useState(null);
  const button = useRef(null);
  const list = useRef(null);
  const id = useId();
  const chosen = options.find((option) => option.value === value);
  const text = display ?? chosen?.label ?? label ?? "";

  const close = (focusButton = true) => { setOpen(false); if (focusButton) button.current?.focus(); };
  const choose = (option) => { if (option.value !== value) onChange(option.value); close(); };
  const openList = (startAt) => {
    const index = startAt ?? Math.max(0, options.findIndex((option) => option.value === value));
    setCursor(index); setOpen(true);
  };

  // 버튼 바로 아래(공간이 없으면 위)에 목록을 둔다. 창 크기나 스크롤이 바뀌면 닫는다: 위치를 쫓아가는 것보다 단순하고 어긋나지 않는다.
  useLayoutEffect(() => {
    if (!open) return;
    const rect = (anchor === "parent" ? button.current.parentElement : button.current).getBoundingClientRect();
    const estimated = Math.min(options.length, 10) * 36 + 10;
    const below = window.innerHeight - rect.bottom >= estimated || rect.top < estimated;
    const gap = anchor === "parent" ? 0 : 4;
    setPosition({ top: below ? rect.bottom + gap : null, bottom: below ? null : window.innerHeight - rect.top + gap,
                  left: align === "right" ? null : rect.left, right: align === "right" ? window.innerWidth - rect.right : null, minWidth: rect.width });
    list.current?.focus();
    const onScroll = (event) => { if (!list.current?.contains(event.target)) close(false); };
    const onPointer = (event) => { if (!list.current?.contains(event.target) && !button.current?.contains(event.target)) close(false); };
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", onScroll);
    document.addEventListener("pointerdown", onPointer);
    return () => { window.removeEventListener("scroll", onScroll, true); window.removeEventListener("resize", onScroll); document.removeEventListener("pointerdown", onPointer); };
  }, [open, options.length, align, anchor]);

  useEffect(() => {
    if (!open) return;
    list.current?.children[cursor]?.scrollIntoView({ block: "nearest" });
  }, [open, cursor]);

  const onButtonKey = (event) => {
    if (["ArrowDown", "ArrowUp", "Enter", " "].includes(event.key)) { event.preventDefault(); openList(event.key === "ArrowUp" ? options.length - 1 : undefined); }
  };
  const onListKey = (event) => {
    const last = options.length - 1;
    if (event.key === "Escape" || event.key === "Tab") { event.preventDefault(); close(); }
    else if (event.key === "ArrowDown") { event.preventDefault(); setCursor((i) => Math.min(last, i + 1)); }
    else if (event.key === "ArrowUp") { event.preventDefault(); setCursor((i) => Math.max(0, i - 1)); }
    else if (event.key === "Home") { event.preventDefault(); setCursor(0); }
    else if (event.key === "End") { event.preventDefault(); setCursor(last); }
    else if (event.key === "Enter" || event.key === " ") { event.preventDefault(); if (options[cursor]) choose(options[cursor]); }
  };

  return <>
    <button ref={button} type="button" className={`dd-button ${buttonClassName} ${active ? "is-active" : ""}`} aria-haspopup="listbox" aria-expanded={open}
      aria-controls={open ? `${id}-list` : undefined} aria-label={label ? `${label}: ${text}` : undefined} title={label} onClick={() => (open ? close() : openList())} onKeyDown={onButtonKey}>
      <span className="dd-button-text">{text}</span><span className="dd-mark" aria-hidden="true" />
    </button>
    {open && position && createPortal(
      <ul ref={list} id={`${id}-list`} className="dd-list" role="listbox" tabIndex={-1} aria-label={label} aria-activedescendant={`${id}-${cursor}`}
        style={{ top: position.top ?? undefined, bottom: position.bottom ?? undefined, left: position.left ?? undefined, right: position.right ?? undefined, minWidth: position.minWidth }}
        onKeyDown={onListKey}>
        {options.map((option, index) => (
          <li key={option.value} id={`${id}-${index}`} role="option" aria-selected={option.value === value}
            className={`dd-option ${index === cursor ? "is-cursor" : ""}`}
            onPointerMove={() => setCursor(index)} onClick={() => choose(option)}>
            {option.label}
          </li>
        ))}
      </ul>, document.body)}
  </>;
}
