import { Easing, interpolate, useCurrentFrame } from "remotion";
import { BrandMark, SafeFrame } from "./scene-style";

export const OutroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 18, 75, 90], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  return (
    <SafeFrame>
      <div style={{ opacity, marginTop: 120 }}>
        <BrandMark />
        <div
          style={{
            marginTop: 260,
            fontFamily: '"Iowan Old Style", "Palatino Linotype", serif',
            fontSize: 122,
            fontWeight: 700,
            letterSpacing: "-6px",
            lineHeight: 0.95,
          }}
        >
          Skip the search. Find the deal.
        </div>
      </div>
      <div style={{ marginTop: "auto", color: "#136f63", fontSize: 42, fontWeight: 800 }}>
        dealledger.eu/us
      </div>
    </SafeFrame>
  );
};
