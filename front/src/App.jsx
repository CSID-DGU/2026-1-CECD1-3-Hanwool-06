import { useState, useEffect } from "react";
import Dashboard from "./pages/Dashboard/Dashboard.jsx";
import DetailPage from "./pages/Detail/DetailPage.jsx";
import SummaryPopup from "./components/SummaryPopup.jsx";
import "./pages/Detail/detail.css";

// 라우터 붙기 전 임시 분기: 주소 끝에 #/detail 이면 디테일 화면, 아니면 대시보드
export default function App() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const onChange = () => setHash(window.location.hash);
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  const isDetail = hash.startsWith("#/detail");
  return (
    <>
      {/* 접속 시 에이전트가 당일 이상징후를 요약해 띄우는 팝업 */}
      <SummaryPopup />
      {isDetail ? <DetailPage /> : <Dashboard />}
    </>
  );
}
