import { Easing, interpolate, useCurrentFrame } from "remotion";
import { BrandMark, SafeFrame } from "./scene-style";

export const SlideshowCtaScene: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 10, 52, 60], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  return (
    <SafeFrame>
      <div style={{ opacity, paddingTop: 36 }}>
        <BrandMark />
        <div
          style={{
            marginTop: 112,
            maxWidth: 820,
            fontFamily: '"Iowan Old Style", "Palatino Linotype", serif',
            fontSize: 124,
            fontWeight: 700,
            letterSpacing: "-6px",
            lineHeight: 0.9,
          }}
        >
          Find your next deal.
        </div>
        <div style={{ marginTop: 42, maxWidth: 720, color: "#486057", fontSize: 47, fontWeight: 650, lineHeight: 1.12 }}>
          Fresh Amazon US deals, reviewed before publishing.
        </div>
        <div
          style={{
            display: "inline-flex",
            marginTop: 66,
            borderRadius: 999,
            backgroundColor: "#136f63",
            color: "#fffdf9",
            padding: "24px 36px",
            fontSize: 42,
            fontWeight: 850,
          }}
        >
          dealledger.eu/us
        </div>
        <div
          style={{
            marginTop: 64,
            width: 840,
            borderRadius: 44,
            backgroundColor: "#136f63",
            color: "#fffdf9",
            padding: "38px 42px",
          }}
        >
          <div style={{ color: "#bde0d4", fontSize: 27, fontWeight: 850, letterSpacing: "0.11em" }}>FREE TO USE</div>
          <div style={{ marginTop: 10, fontSize: 48, fontWeight: 850, letterSpacing: "-1.6px" }}>Browse deals. Save favourites. Get alerts.</div>
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
          ["US picks", "Deal Ledger"],
          ["Save deals", "Your favourites"],
          ["Get alerts", "When prices change"],
        ].map(([title, detail]) => (
          <div key={title} style={{ borderRadius: 30, backgroundColor: "#fffdf9", boxShadow: "0 14px 30px rgba(29, 43, 36, 0.1)", padding: "34px 24px" }}>
            <div style={{ color: "#1d2b24", fontSize: 39, fontWeight: 900 }}>{title}</div>
            <div style={{ marginTop: 7, color: "#486057", fontSize: 24, fontWeight: 700, lineHeight: 1.05 }}>{detail}</div>
          </div>
        ))}
      </div>
    </SafeFrame>
  );
};
