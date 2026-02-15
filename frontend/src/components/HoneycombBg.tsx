const S = 28; // hex side length -- tweak for cell size
const H = S * Math.sqrt(3); // hex height
const PW = S * 3; // pattern tile width
const PH = H; // pattern tile height

// Flat-top hexagon vertices centered at (cx, cy)
function hex(cx: number, cy: number) {
  const pts = [
    [cx + S, cy],
    [cx + S / 2, cy + H / 2],
    [cx - S / 2, cy + H / 2],
    [cx - S, cy],
    [cx - S / 2, cy - H / 2],
    [cx + S / 2, cy - H / 2],
  ];
  return pts.map((p) => p.join(",")).join(" ");
}

// Five hex centers tile seamlessly in a (3s x h) rectangle
const HEX_CENTERS: [number, number][] = [
  [0, 0],
  [PW, 0],
  [0, PH],
  [PW, PH],
  [PW / 2, PH / 2],
];

export default function HoneycombBg() {
  return (
    <div className="fixed inset-0 -z-10">
      <svg
        className="absolute inset-0 w-full h-full"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <defs>
          <filter id="honey-noise" x="0" y="0" width="100%" height="100%">
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.012"
              numOctaves="3"
              seed="7"
              result="noise"
            />
            <feColorMatrix
              type="matrix"
              in="noise"
              values="0.012 0 0 0 0.988
                      0 0.073 0 0 0.886
                      0 0 0.173 0 0.678
                      0 0 0 0 1"
            />
          </filter>

          <pattern
            id="hex-grid"
            width={PW}
            height={PH}
            patternUnits="userSpaceOnUse"
          >
            {HEX_CENTERS.map(([cx, cy], i) => (
              <polygon
                key={i}
                points={hex(cx, cy)}
                fill="none"
                stroke="white"
                strokeWidth="3"
              />
            ))}
          </pattern>
        </defs>

        {/* Noise layer */}
        <rect width="100%" height="100%" filter="url(#honey-noise)" />
        {/* Hex grid layer */}
        <rect width="100%" height="100%" fill="url(#hex-grid)" />
      </svg>
    </div>
  );
}
