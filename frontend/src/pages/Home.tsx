import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import avatarImg from "@/assets/avatar.png";
import captionImg from "@/assets/caption.png";
import titleImg from "@/assets/title.png";

export default function Home() {
  const navigate = useNavigate();

  return (
    <div className="relative h-screen overflow-hidden">
      {/* Illustration layer */}
      <div className="absolute inset-0 pointer-events-none select-none" aria-hidden="true">
        <img
          src={titleImg}
          alt=""
          className="absolute left-[8%] top-[0px] w-[680px]"
          draggable={false}
        />
        <img
          src={avatarImg}
          alt=""
          className="absolute right-[120px] bottom-[-40px] h-[82vh]"
          draggable={false}
        />
        <img
          src={captionImg}
          alt=""
          className="absolute right-[90px] bottom-[570px] w-[300px]"
          draggable={false}
        />
      </div>

      {/* Content layer */}
      <div className="relative z-10 h-full">
        <div className="absolute left-[8%] top-[500px] w-[680px] flex justify-center">
          <Button
            className="text-2xl px-14 py-5 h-auto"
            onClick={() => navigate("/sessions")}
          >
            Get Started
          </Button>
        </div>
      </div>
    </div>
  );
}
