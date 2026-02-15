import { Routes, Route } from "react-router-dom";
import HoneycombBg from "@/components/HoneycombBg";
import Home from "@/pages/Home";
import Sessions from "@/pages/Sessions";
import SessionView from "@/pages/SessionView";
import NewSessionView from "@/pages/NewSessionView";
import IframeTest from "@/pages/IframeTest";

export default function App() {
  return (
    <>
      <HoneycombBg />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/sessions" element={<Sessions />} />
        <Route path="/sessions/:id" element={<SessionView />} />
        <Route path="/sessions/:id/new" element={<NewSessionView />} />
        <Route path="/iframe-test" element={<IframeTest />} />
      </Routes>
    </>
  );
}
