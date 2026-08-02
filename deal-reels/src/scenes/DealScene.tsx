import { Easing, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import type { Deal } from "../types";
import { BrandMark, SafeFrame } from "./scene-style";

const money = (amount: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: amount % 1 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(amount);

export const DealScene: React.FC<{ deal: Deal; rank: number; durationInFrames: number }> = ({ deal, rank, durationInFrames }) => {
  const frame = useCurrentFrame();
  const exitStart = Math.max(40, durationInFrames - 22);
  const productOpacity = interpolate(frame, [0, 16, exitStart, durationInFrames], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const productScale = interpolate(frame, [0, exitStart], [0.9, 1.03], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const copyOpacity = interpolate(frame, [12, 35, exitStart, durationInFrames], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const savings = Math.round(deal.discountPct * 100);

  return (
    <SafeFrame>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <BrandMark />
        <div style={{ color: "#136f63", fontSize: 28, fontWeight: 800, letterSpacing: "0.14em" }}>
          PICK {rank}
        </div>
      </div>

      <div style={{ display: "flex", flex: 1, alignItems: "center", justifyContent: "center" }}>
        <div
          style={{
            width: 830,
            height: 760,
            borderRadius: 58,
            backgroundColor: "#fffdf9",
            boxShadow: "0 32px 80px rgba(29, 43, 36, 0.16)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            overflow: "hidden",
            opacity: productOpacity,
          }}
        >
          <Img
            src={staticFile(deal.imagePath)}
            style={{ width: "84%", height: "84%", objectFit: "contain", scale: productScale }}
          />
        </div>
      </div>

      <div style={{ opacity: copyOpacity }}>
        <div style={{ color: "#136f63", fontSize: 72, fontWeight: 900, letterSpacing: "-3px" }}>
          {savings}% off
        </div>
        <div
          style={{
            marginTop: 12,
            maxWidth: 850,
            fontFamily: '"Iowan Old Style", "Palatino Linotype", serif',
            fontSize: 76,
            fontWeight: 700,
            letterSpacing: "-3.4px",
            lineHeight: 0.99,
          }}
        >
          {deal.shortTitle}
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 28, marginTop: 34 }}>
          <div style={{ color: "#1d2b24", fontSize: 70, fontWeight: 800 }}>{money(deal.salePrice)}</div>
          <div style={{ color: "#718078", fontSize: 38, fontWeight: 600, textDecoration: "line-through" }}>
            {money(deal.listPrice)}
          </div>
        </div>
        <div style={{ marginTop: 34, color: "#52635a", fontSize: 29, fontWeight: 700 }}>
          Amazon US · Public price checked
        </div>
      </div>
    </SafeFrame>
  );
};
