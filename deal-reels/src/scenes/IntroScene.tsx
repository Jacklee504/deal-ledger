import { Easing, interpolate, useCurrentFrame } from "remotion";
import { BrandMark, SafeFrame } from "./scene-style";

export const IntroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 18, 102, 120], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const lift = interpolate(frame, [0, 24], [32, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  return (
    <SafeFrame>
      <div style={{ opacity, translate: `0 ${lift}px`, marginTop: 46 }}>
        <BrandMark />
        <div
          style={{
            marginTop: 160,
            maxWidth: 780,
            fontFamily: '"Iowan Old Style", "Palatino Linotype", serif',
            fontSize: 126,
            fontWeight: 700,
            letterSpacing: "-6px",
            lineHeight: 0.94,
          }}
        >
          Today’s strongest deals.
        </div>
        <div
          style={{
            marginTop: 52,
            color: "#486057",
            fontSize: 45,
            fontWeight: 600,
            letterSpacing: "0.02em",
          }}
        >
          Amazon US, reviewed before publishing
        </div>
      </div>
      <div
        style={{
          marginTop: "auto",
          color: "#136f63",
          fontSize: 32,
          fontWeight: 800,
          letterSpacing: "0.13em",
          textTransform: "uppercase",
        }}
      >
        Price context, without the noise
      </div>
    </SafeFrame>
  );
};
