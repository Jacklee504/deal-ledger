import type { CSSProperties, FC, PropsWithChildren } from "react";
import { AbsoluteFill } from "remotion";

export const frameStyle: CSSProperties = {
  background:
    "radial-gradient(circle at 88% 8%, rgba(241, 197, 122, 0.72), transparent 26%), radial-gradient(circle at 4% 88%, rgba(164, 215, 203, 0.7), transparent 30%), #f6f1e8",
  color: "#1d2b24",
  overflow: "hidden",
};

export const SafeFrame: FC<PropsWithChildren> = ({ children }) => (
  <AbsoluteFill style={frameStyle}>
    <div
      style={{
        position: "absolute",
        inset: 96,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div style={{ display: "flex", flex: 1, flexDirection: "column", position: "relative" }}>{children}</div>
    </div>
  </AbsoluteFill>
);

export const BrandMark: FC<{ inverse?: boolean }> = ({ inverse = false }) => (
  <div
    style={{
      color: inverse ? "#fffdf9" : "#136f63",
      fontFamily: '"Iowan Old Style", "Palatino Linotype", serif',
      fontSize: 46,
      fontWeight: 700,
      letterSpacing: "-1.5px",
    }}
  >
    Deal Ledger
  </div>
);
