import { Routes, Route } from "react-router-dom";
import HoneycombBg from "@/components/HoneycombBg";
import Home from "@/pages/Home";
import Sessions from "@/pages/Sessions";
import NewSessionView from "@/pages/NewSessionView";

export default function App() {
  return (
    <>
      <HoneycombBg />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/sessions" element={<Sessions />} />
        <Route path="/sessions/:id" element={<NewSessionView />} />
      </Routes>
    </>
  );
}
