import { Img, staticFile } from "remotion";
import { SafeFrame } from "./scene-style";
import type { Deal } from "../types";

export const CoverScene: React.FC<{ deals: Deal[] }> = ({ deals }) => {
  const highestDiscount = Math.max(...deals.map((deal) => Math.round(deal.discountPct * 100)));

  return (
    <SafeFrame>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gridTemplateRows: "1fr 1fr",
          gap: 28,
          flex: 1,
          minHeight: 0,
        }}
      >
        <div
          style={{
            borderRadius: 48,
            background: "#17332e",
            boxShadow: "0 24px 52px rgba(29, 43, 36, 0.16)",
            color: "#fffdf9",
            padding: 52,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div style={{ color: "#f1c57a", fontSize: 24, fontWeight: 850, letterSpacing: "0.14em" }}>AMAZON US</div>
          <div>
            <Img src={staticFile("brand/deal-ledger-logo-circle.svg")} style={{ height: 152, width: 152 }} />
            <div style={{ marginTop: 27, fontFamily: '"Iowan Old Style", "Palatino Linotype", serif', fontSize: 72, fontWeight: 700, letterSpacing: "-3px", lineHeight: 0.9 }}>Deal<br />Ledger</div>
          </div>
          <div style={{ color: "#d7e8df", fontSize: 29, fontWeight: 650, lineHeight: 1.12 }}>
            Today’s roundup<br />Up to <span style={{ color: "#f1c57a", fontWeight: 900 }}>{highestDiscount}% off</span>
          </div>
        </div>
        {deals.map((deal) => (
          <div
            key={deal.asin}
            style={{
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              borderRadius: 48,
              background: "#fffdf9",
              boxShadow: "0 24px 52px rgba(29, 43, 36, 0.12)",
            }}
          >
            <div style={{ flex: 1, minHeight: 0, display: "flex", alignItems: "center", justifyContent: "center", padding: 28 }}>
              <Img src={staticFile(deal.imagePath)} style={{ width: "100%", height: "100%", objectFit: "contain" }} />
            </div>
            <div style={{ background: "#136f63", color: "#fffdf9", padding: "23px 28px 25px", textAlign: "center" }}>
              <div style={{ color: "#bde3d5", fontSize: 20, fontWeight: 850, letterSpacing: "0.12em" }}>SAVE</div>
              <div style={{ fontSize: 66, fontWeight: 900, letterSpacing: "-3px", lineHeight: 0.94 }}>{Math.round(deal.discountPct * 100)}% OFF</div>
            </div>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 38, color: "#136f63", fontSize: 30, fontWeight: 850, letterSpacing: "0.02em", textAlign: "center" }}>dealledger.eu/us</div>
    </SafeFrame>
  );
};
