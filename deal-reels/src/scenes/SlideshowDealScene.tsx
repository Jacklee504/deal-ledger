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

export const SlideshowDealScene: React.FC<{ deal: Deal; rank: number; durationInFrames: number }> = ({
  deal,
  rank,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const exitStart = Math.max(44, durationInFrames - 10);
  const opacity = interpolate(frame, [0, 8, exitStart, durationInFrames], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const imageScale = interpolate(frame, [0, durationInFrames], [0.98, 1.035], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const savings = Math.round(deal.discountPct * 100);
  const savedAmount = deal.listPrice - deal.salePrice;

  return (
    <SafeFrame>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", opacity }}>
        <BrandMark />
        <div style={{ color: "#136f63", fontSize: 31, fontWeight: 900, letterSpacing: "0.14em" }}>DEAL 0{rank}</div>
      </div>

      {/** The bottom 25% stays intentionally empty for TikTok/Reels chrome. */}
      <div style={{ opacity, marginTop: 44, position: "relative", height: 1230 }}>
        <div
          style={{
            position: "absolute",
            right: 0,
            top: 0,
            zIndex: 2,
            minWidth: 255,
            borderRadius: 999,
            backgroundColor: "#d95836",
            color: "#fffdf9",
            padding: "25px 36px 28px",
            fontSize: 72,
            fontWeight: 950,
            letterSpacing: "-3px",
            textAlign: "center",
            boxShadow: "0 18px 30px rgba(133, 61, 38, 0.2)",
          }}
        >
          {savings}%<span style={{ display: "block", marginTop: 2, fontSize: 26, letterSpacing: "0.09em" }}>OFF</span>
        </div>
        <div
          style={{
            height: 810,
            borderRadius: 60,
            backgroundColor: "#fffdf9",
            boxShadow: "0 28px 70px rgba(29, 43, 36, 0.16)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            overflow: "hidden",
          }}
        >
          <Img src={staticFile(deal.imagePath)} style={{ width: "83%", height: "83%", objectFit: "contain", scale: imageScale }} />
        </div>
        <div
          style={{
            marginTop: 38,
            maxWidth: 825,
            fontFamily: '"Iowan Old Style", "Palatino Linotype", serif',
            fontSize: 60,
            fontWeight: 700,
            letterSpacing: "-2.6px",
            lineHeight: 0.96,
          }}
        >
          {deal.shortTitle}
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 26, marginTop: 26 }}>
          <div style={{ color: "#1d2b24", fontSize: 73, fontWeight: 900, letterSpacing: "-2px" }}>{money(deal.salePrice)}</div>
          <div style={{ color: "#718078", fontSize: 36, fontWeight: 700, textDecoration: "line-through" }}>{money(deal.listPrice)}</div>
        </div>
        <div style={{ marginTop: 20, color: "#486057", fontSize: 28, fontWeight: 750, letterSpacing: "0.04em" }}>AMAZON US · PUBLIC PRICE CHECKED</div>
        <div style={{ marginTop: 28, color: "#136f63", fontSize: 30, fontWeight: 900, letterSpacing: "0.12em" }}>NEXT PICK →</div>
      </div>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 2,
          borderRadius: 34,
          backgroundColor: "#1d2b24",
          color: "#fffdf9",
          padding: "26px 32px",
          display: "flex",
          alignItems: "center",
        }}
      >
        {/** The lower-left segment is intentionally non-essential because social UI may cover it. */}
        <div style={{ width: 180, color: "#bde0d4", fontSize: 22, fontWeight: 850, letterSpacing: "0.09em", lineHeight: 1.15 }}>AMAZON US<br />DEAL LEDGER</div>
        <div style={{ flex: 1, paddingLeft: 26 }}>
          <div style={{ color: "#bde0d4", fontSize: 24, fontWeight: 850, letterSpacing: "0.1em" }}>TODAY’S SAVING</div>
          <div style={{ marginTop: 5, color: "#f1c57a", fontSize: 57, fontWeight: 950, letterSpacing: "-2px" }}>{money(savedAmount)}</div>
        </div>
        <div style={{ fontSize: 29, fontWeight: 850, letterSpacing: "0.04em", textAlign: "right" }}>PICK {rank} OF 3<br />DEAL LEDGER →</div>
      </div>
    </SafeFrame>
  );
};
