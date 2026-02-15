import { useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { Button } from "@/components/ui/button";
import avatarImg from "@/assets/avatar.png";
import captionImg from "@/assets/caption.png";
import titleImg from "@/assets/title.png";

const SPLASH_TEXT = "A Browser Agent Hive that Builds Knowledge Bases";
const CHAR_STAGGER = 0.03;
const FADE_IN = 1.2;
const HOLD = 2.0;
const FADE_OUT = 1.2;
const PAUSE = 1.0;
const TOTAL = FADE_IN + HOLD + FADE_OUT + PAUSE;

function RippleText() {
  const chars = SPLASH_TEXT.split("");

  return (
    <span aria-label={SPLASH_TEXT}>
      {chars.map((ch, i) => (
        <motion.span
          key={i}
          aria-hidden
          className="inline-block"
          style={{ whiteSpace: ch === " " ? "pre" : undefined }}
          initial={{ opacity: 0 }}
          animate={{ opacity: [0, 1, 1, 0] }}
          transition={{
            duration: TOTAL,
            times: [
              0,
              FADE_IN / TOTAL,
              (FADE_IN + HOLD) / TOTAL,
              (FADE_IN + HOLD + FADE_OUT) / TOTAL,
            ],
            delay: i * CHAR_STAGGER,
            repeat: Infinity,
            repeatDelay: chars.length * CHAR_STAGGER,
            ease: "easeInOut",
          }}
        >
          {ch}
        </motion.span>
      ))}
    </span>
  );
}

export default function Home() {
  const navigate = useNavigate();

  return (
    <div className="relative h-screen overflow-hidden">
      {/* Illustration layer */}
      <div className="absolute inset-0 pointer-events-none select-none" aria-hidden="true">
        <img
          src={titleImg}
          alt=""
          className="absolute left-[14%] top-[100px] w-[480px]"
          draggable={false}
        />
        <img
          src={avatarImg}
          alt=""
          className="absolute right-[120px] bottom-[-40px] h-[82vh]"
          draggable={false}
        />
        <motion.img
          src={captionImg}
          alt=""
          className="absolute right-[90px] bottom-[570px] w-[300px]"
          draggable={false}
          style={{ transformOrigin: "bottom left" }}
          initial={{ rotate: -90, opacity: 0 }}
          animate={{ rotate: 0, opacity: 1 }}
          transition={{
            rotate: {
              type: "spring",
              stiffness: 260,
              damping: 8,
              delay: 3,
            },
            opacity: { duration: 0.05, delay: 3 },
          }}
        />
      </div>

      {/* Content layer */}
      <div className="relative z-10 h-full">
        <div className="absolute left-[8%] top-[440px] w-[680px] text-center">
          <p className="text-2xl text-bee-black/80 tracking-wide">
            <RippleText />
          </p>
        </div>
        <div className="absolute left-[8%] top-[500px] w-[680px] flex justify-center">
          <Button
            className="text-2xl px-14 py-5 h-auto"
            onClick={() => navigate("/sessions")}
          >
            Get Started
          </Button>
        </div>

        <div className="absolute bottom-6 left-6 flex gap-4 text-sm text-bee-black/40">
          <a href="https://devpost.com/software/beework" target="_blank" rel="noopener noreferrer" className="hover:text-bee-black/70 transition-colors">Devpost</a>
          <a href="https://github.com/Alezander9/BeeWork" target="_blank" rel="noopener noreferrer" className="hover:text-bee-black/70 transition-colors">Github</a>
          <a href="#" target="_blank" rel="noopener noreferrer" className="hover:text-bee-black/70 transition-colors">Pitch Deck</a>
          <a href="/buy" className="hover:text-bee-black/70 transition-colors">Buy Now</a>
        </div>
      </div>
    </div>
  );
}
