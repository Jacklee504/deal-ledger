import { Easing, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import type { Deal } from "../types";
import { BrandMark, SafeFrame } from "./scene-style";

export const SlideshowHookScene: React.FC<{ deals: Deal[] }> = ({ deals }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 10, 52, 60], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const lift = interpolate(frame, [0, 14], [26, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const strongestDiscount = Math.max(...deals.map((deal) => Math.round(deal.discountPct * 100)));

  return (
    <SafeFrame>
      <div style={{ opacity, translate: `0 ${lift}px`, paddingTop: 36 }}>
        <BrandMark />
        <div style={{ marginTop: 94, color: "#136f63", fontSize: 34, fontWeight: 900, letterSpacing: "0.12em" }}>
          AMAZON US DEALS
        </div>
        <div
          style={{
            marginTop: 26,
            maxWidth: 820,
            fontFamily: '"Iowan Old Style", "Palatino Linotype", serif',
            fontSize: 128,
            fontWeight: 700,
            letterSpacing: "-6px",
            lineHeight: 0.9,
          }}
        >
          Stop paying full price.
        </div>
        <div style={{ marginTop: 40, maxWidth: 720, color: "#486057", fontSize: 47, fontWeight: 650, lineHeight: 1.12 }}>
          Three worthwhile reductions, checked before they go live.
        </div>
        <div
          style={{
            display: "inline-flex",
            marginTop: 58,
            borderRadius: 999,
            backgroundColor: "#136f63",
            color: "#fffdf9",
            padding: "22px 34px",
            fontSize: 35,
            fontWeight: 850,
            letterSpacing: "0.03em",
          }}
        >
          SEE TODAY’S PICKS →
        </div>
        <div
          style={{
            marginTop: 58,
            width: 840,
            borderRadius: 44,
            backgroundColor: "#1d2b24",
            color: "#fffdf9",
            padding: "36px 40px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div style={{ color: "#bde0d4", fontSize: 27, fontWeight: 850, letterSpacing: "0.11em" }}>TODAY’S ROUND-UP</div>
            <div style={{ marginTop: 12, fontSize: 42, fontWeight: 800 }}>{deals.length} reviewed deals</div>
          </div>
          <div style={{ color: "#f1c57a", fontSize: 74, fontWeight: 950, letterSpacing: "-3px" }}>UP TO {strongestDiscount}%</div>
        </div>
        <div style={{ display: "flex", gap: 20, marginTop: 36 }}>
          {deals.map((deal, index) => (
            <div
              key={deal.asin}
              style={{
                width: 267,
                height: 190,
                borderRadius: 30,
                backgroundColor: "#fffdf9",
                boxShadow: "0 14px 30px rgba(29, 43, 36, 0.11)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                overflow: "hidden",
                position: "relative",
              }}
            >
              <Img src={staticFile(deal.imagePath)} style={{ width: "84%", height: "80%", objectFit: "contain" }} />
              <div style={{ position: "absolute", left: 14, top: 13, color: "#d95836", fontSize: 25, fontWeight: 950 }}>{Math.round(deal.discountPct * 100)}%</div>
              <div style={{ position: "absolute", right: 14, top: 13, color: "#718078", fontSize: 21, fontWeight: 850 }}>0{index + 1}</div>
            </div>
          ))}
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 2,
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 14,
        }}
      >
        {[
          ["US", "Amazon picks"],
          ["UP TO", `${strongestDiscount}% off`],
          ["TODAY", `${deals.length} deals`],
        ].map(([index, label]) => (
          <div key={index} style={{ borderTop: "3px solid #136f63", paddingTop: 16 }}>
            <div style={{ color: "#d95836", fontSize: 27, fontWeight: 950 }}>{index}</div>
            <div style={{ marginTop: 8, color: "#1d2b24", fontSize: 31, fontWeight: 850, lineHeight: 1.03 }}>{label}</div>
          </div>
        ))}
      </div>
    </SafeFrame>
  );
};
