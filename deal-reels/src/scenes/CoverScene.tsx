import { Img, staticFile } from "remotion";
import { SafeFrame } from "./scene-style";
import type { Deal } from "../types";

export const CoverScene: React.FC<{ deals: Deal[]; square?: boolean; social?: boolean }> = ({ deals, square = false, social = false }) => {
  const highestDiscount = Math.max(...deals.map((deal) => Math.round(deal.discountPct * 100)));

  if (social) {
    return (
      <SafeFrame>
        <div style={{ display: "flex", flexDirection: "column", flex: 1, gap: 24, minHeight: 0 }}>
          <div
            style={{
              flex: "0 0 216px",
              borderRadius: 42,
              background: "#17332e",
              boxShadow: "0 24px 52px rgba(29, 43, 36, 0.16)",
              color: "#fffdf9",
              display: "flex",
              alignItems: "center",
              padding: "32px 38px",
              gap: 28,
            }}
          >
            <Img src={staticFile("brand/deal-ledger-logo-circle.svg")} style={{ width: 126, height: 126, flexShrink: 0 }} />
            <div style={{ minWidth: 0 }}>
              <div style={{ color: "#f1c57a", fontSize: 20, fontWeight: 850, letterSpacing: "0.14em" }}>AMAZON US · TODAY’S DEALS</div>
              <div style={{ marginTop: 9, fontFamily: '"Iowan Old Style", "Palatino Linotype", serif', fontSize: 62, fontWeight: 700, letterSpacing: "-2px", lineHeight: 0.9 }}>Deal Ledger</div>
              <div style={{ marginTop: 13, color: "#d7e8df", fontSize: 27, fontWeight: 700 }}>Save up to <span style={{ color: "#f1c57a", fontWeight: 900 }}>{highestDiscount}%</span> today</div>
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0, gap: 22 }}>
            {deals.map((deal) => (
              <div
                key={deal.asin}
                style={{
                  flex: 1,
                  display: "flex",
                  overflow: "hidden",
                  borderRadius: 38,
                  background: "#fffdf9",
                  boxShadow: "0 20px 42px rgba(29, 43, 36, 0.12)",
                }}
              >
                <div style={{ flex: 1, minWidth: 0, display: "flex", alignItems: "center", justifyContent: "center", padding: "18px 38px" }}>
                  <Img src={staticFile(deal.imagePath)} style={{ width: "100%", height: "100%", objectFit: "contain" }} />
                </div>
                <div style={{ width: 255, background: "#136f63", color: "#fffdf9", display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", padding: 20, textAlign: "center" }}>
                  <div style={{ color: "#bde3d5", fontSize: 18, fontWeight: 850, letterSpacing: "0.12em" }}>SAVE</div>
                  <div style={{ marginTop: 4, fontSize: 61, fontWeight: 900, letterSpacing: "-3px", lineHeight: 0.9 }}>{Math.round(deal.discountPct * 100)}%</div>
                  <div style={{ marginTop: 3, fontSize: 22, fontWeight: 850, letterSpacing: "0.09em" }}>OFF</div>
                </div>
              </div>
            ))}
          </div>
          <div style={{ color: "#136f63", fontSize: 23, fontWeight: 850, letterSpacing: "0.02em", textAlign: "center" }}>dealledger.eu/us</div>
        </div>
      </SafeFrame>
    );
  }

  const tileRadius = square ? 32 : 48;
  const logoPadding = square ? 30 : 52;
  const productPadding = square ? 16 : 28;
  const discountPadding = square ? "12px 14px 14px" : "23px 28px 25px";

  return (
    <SafeFrame>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gridTemplateRows: "1fr 1fr",
          gap: square ? 20 : 28,
          flex: 1,
          minHeight: 0,
        }}
      >
        <div
          style={{
            borderRadius: tileRadius,
            background: "#17332e",
            boxShadow: "0 24px 52px rgba(29, 43, 36, 0.16)",
            color: "#fffdf9",
            padding: logoPadding,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div style={{ color: "#f1c57a", fontSize: square ? 16 : 24, fontWeight: 850, letterSpacing: "0.14em" }}>AMAZON US</div>
          <div>
            <Img src={staticFile("brand/deal-ledger-logo-circle.svg")} style={{ height: square ? 86 : 152, width: square ? 86 : 152 }} />
            <div style={{ marginTop: square ? 15 : 27, fontFamily: '"Iowan Old Style", "Palatino Linotype", serif', fontSize: square ? 44 : 72, fontWeight: 700, letterSpacing: square ? "-2px" : "-3px", lineHeight: 0.9 }}>Deal<br />Ledger</div>
          </div>
          <div style={{ color: "#d7e8df", fontSize: square ? 18 : 29, fontWeight: 650, lineHeight: 1.12 }}>
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
              borderRadius: tileRadius,
              background: "#fffdf9",
              boxShadow: "0 24px 52px rgba(29, 43, 36, 0.12)",
            }}
          >
            <div style={{ flex: 1, minHeight: 0, display: "flex", alignItems: "center", justifyContent: "center", padding: productPadding }}>
              <Img src={staticFile(deal.imagePath)} style={{ width: "100%", height: "100%", objectFit: "contain" }} />
            </div>
            <div style={{ background: "#136f63", color: "#fffdf9", padding: discountPadding, textAlign: "center" }}>
              <div style={{ color: "#bde3d5", fontSize: square ? 12 : 20, fontWeight: 850, letterSpacing: "0.12em" }}>SAVE</div>
              <div style={{ fontSize: square ? 38 : 66, fontWeight: 900, letterSpacing: square ? "-2px" : "-3px", lineHeight: 0.94 }}>{Math.round(deal.discountPct * 100)}% OFF</div>
            </div>
          </div>
        ))}
      </div>
      <div style={{ marginTop: square ? 18 : 38, color: "#136f63", fontSize: square ? 18 : 30, fontWeight: 850, letterSpacing: "0.02em", textAlign: "center" }}>dealledger.eu/us</div>
    </SafeFrame>
  );
};
