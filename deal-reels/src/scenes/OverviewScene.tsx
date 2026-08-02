import type { FC, ReactNode } from "react";
import { Easing, interpolate, useCurrentFrame } from "remotion";
import { BrandMark, SafeFrame } from "./scene-style";

const Check: FC<{ children: ReactNode; delay: number }> = ({ children, delay }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [delay, delay + 14], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 24, opacity, marginTop: 34 }}>
      <div
        style={{
          width: 42,
          height: 42,
          borderRadius: 21,
          display: "grid",
          placeItems: "center",
          color: "#fffdf9",
          background: "#136f63",
          fontSize: 26,
          fontWeight: 900,
        }}
      >
        ✓
      </div>
      <div style={{ fontSize: 42, fontWeight: 650 }}>{children}</div>
    </div>
  );
};

export const OverviewScene: React.FC = () => {
  const frame = useCurrentFrame();
  const panelOpacity = interpolate(frame, [0, 20, 130, 150], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const panelLift = interpolate(frame, [0, 22], [44, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  return (
    <SafeFrame>
      <BrandMark />
      <div style={{ opacity: panelOpacity, translate: `0 ${panelLift}px`, marginTop: 120 }}>
        <div
          style={{
            fontFamily: '"Iowan Old Style", "Palatino Linotype", serif',
            fontSize: 102,
            fontWeight: 700,
            letterSpacing: "-5px",
            lineHeight: 0.96,
          }}
        >
          Your shortcut to better deals.
        </div>
        <div
          style={{
            marginTop: 74,
            padding: "62px 58px",
            borderRadius: 46,
            background: "#fffdf9",
            boxShadow: "0 28px 65px rgba(29, 43, 36, 0.12)",
          }}
        >
          <Check delay={25}>High-discount finds, picked for you</Check>
          <Check delay={48}>Fresh Amazon deals, all in one place</Check>
          <Check delay={71}>Less searching. More saving.</Check>
        </div>
      </div>
      <div style={{ marginTop: "auto", color: "#136f63", fontSize: 34, fontWeight: 800 }}>
        dealledger.eu/us
      </div>
    </SafeFrame>
  );
};
