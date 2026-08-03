import { AbsoluteFill, Audio, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import reelData from "./data/reel.json";
import type { Deal, ReelData } from "./types";
import { frameStyle } from "./scenes/scene-style";

export type ExplainerVariant = "save-time" | "clear-price" | "personal-alerts";

export const explainerVariants: Record<ExplainerVariant, { audio: string; hook: string; kicker: string }> = {
  "save-time": {
    audio: "audio/explainer-save-time.mp3",
    hook: "Spend less.\nSearch less.",
    kicker: "A free shortcut to worthwhile Amazon deals.",
  },
  "clear-price": {
    audio: "audio/explainer-clear-price.mp3",
    hook: "Too many tabs.\nToo little clarity.",
    kicker: "A better way to check today’s prices.",
  },
  "personal-alerts": {
    audio: "audio/explainer-personal-alerts.mp3",
    hook: "Only see deals\nyou care about.",
    kicker: "Make deal-hunting feel personal.",
  },
};

const reel = reelData as ReelData;
const demoDeals = reel.deals.slice(0, 3);

const eased = (frame: number, start: number, end: number) => interpolate(frame, [start, end], [0, 1], {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
  easing: Easing.bezier(0.16, 1, 0.3, 1),
});

const Brand = ({ inverse = false }: { inverse?: boolean }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
    <Img src={staticFile("brand/deal-ledger-logo-circle.svg")} style={{ width: 58, height: 58 }} />
    <div style={{ color: inverse ? "#fffdf9" : "#17332e", fontFamily: '"Iowan Old Style", "Palatino Linotype", serif', fontSize: 43, fontWeight: 700, letterSpacing: "-1.5px" }}>Deal Ledger</div>
  </div>
);

const DealCard = ({ deal, index, compact = false }: { deal: Deal; index: number; compact?: boolean }) => {
  const frame = useCurrentFrame();
  const enter = eased(frame, 82 + index * 10, 100 + index * 10);
  const lift = interpolate(enter, [0, 1], [56, 0]);
  const discount = Math.round(deal.discountPct * 100);
  return (
    <div style={{ opacity: enter, translate: `0 ${lift}px`, flex: 1, minWidth: 0, borderRadius: compact ? 26 : 34, overflow: "hidden", isolation: "isolate", background: "#fffdf9", boxShadow: "0 22px 44px rgba(29, 43, 36, 0.14)" }}>
      <div style={{ height: compact ? 192 : 280, position: "relative", zIndex: 1, display: "grid", placeItems: "center", overflow: "hidden", padding: compact ? 20 : 28, background: "#fffdf9" }}>
        <Img src={staticFile(deal.imagePath)} style={{ position: "relative", zIndex: 1, display: "block", width: "100%", height: "100%", maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }} />
      </div>
      <div style={{ position: "relative", zIndex: 2, padding: compact ? "14px 18px 16px" : "20px 24px", color: "#fffdf9", background: "#17332e", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
        <div>
          <div style={{ color: "#d7e8df", fontSize: compact ? 11 : 15, fontWeight: 850, letterSpacing: "0.1em" }}>CURRENT PRICE</div>
          <div style={{ marginTop: 2, fontSize: compact ? 25 : 34, fontWeight: 900, lineHeight: 1 }}>${deal.salePrice.toFixed(deal.salePrice % 1 ? 2 : 0)}</div>
        </div>
        <div style={{ flexShrink: 0, color: "#f1c57a", fontSize: compact ? 19 : 25, fontWeight: 900, lineHeight: 1 }}>{discount}% OFF</div>
      </div>
    </div>
  );
};

const CheckRow = ({ label, index, active = true }: { label: string; index: number; active?: boolean }) => {
  const frame = useCurrentFrame();
  const show = eased(frame, 190 + index * 14, 207 + index * 14);
  return <div style={{ opacity: show, translate: `0 ${interpolate(show, [0, 1], [24, 0])}px`, display: "flex", alignItems: "center", gap: 20, padding: "20px 24px", borderRadius: 22, background: active ? "#e6f1ea" : "#f1eee6", fontSize: 30, fontWeight: 750, color: "#17332e" }}>
    <span style={{ display: "grid", placeItems: "center", width: 36, height: 36, borderRadius: 10, color: "#fffdf9", background: active ? "#136f63" : "#9ba79f", fontSize: 23 }}>{active ? "✓" : ""}</span>{label}
  </div>;
};

const SaveTimeLayout = () => {
  const frame = useCurrentFrame();
  const intro = eased(frame, 0, 20);
  const cards = eased(frame, 72, 90);
  const choices = eased(frame, 185, 202);
  const close = eased(frame, 454, 474);
  return <AbsoluteFill style={frameStyle}>
    <div style={{ position: "absolute", inset: 88, display: "flex", flexDirection: "column" }}>
      <div style={{ opacity: intro, translate: `0 ${interpolate(intro, [0, 1], [45, 0])}px` }}><Brand /></div>
      <div style={{ opacity: intro, marginTop: 118, fontFamily: '"Iowan Old Style", "Palatino Linotype", serif', fontSize: 122, lineHeight: 0.92, letterSpacing: "-6px", fontWeight: 700 }}>Spend less.<br />Search less.</div>
      <div style={{ opacity: intro, marginTop: 34, color: "#486057", fontSize: 38, fontWeight: 650, lineHeight: 1.24 }}>Today’s strongest deals, gathered in one simple place.</div>
      <div style={{ opacity: cards, display: "flex", gap: 20, marginTop: 80 }}>{demoDeals.map((deal, index) => <DealCard key={deal.asin} deal={deal} index={index} compact />)}</div>
      <div style={{ opacity: choices, marginTop: 74, borderRadius: 36, padding: "34px 38px", background: "#17332e", color: "#fffdf9" }}>
        <div style={{ color: "#f1c57a", fontSize: 22, fontWeight: 900, letterSpacing: "0.13em" }}>YOUR WATCHLIST</div>
        <div style={{ marginTop: 14, fontSize: 40, fontWeight: 800 }}>Audio · Home office · Robot vacuums</div>
      </div>
      <div style={{ opacity: close, marginTop: "auto", paddingBottom: 4 }}><div style={{ color: "#136f63", fontSize: 53, fontWeight: 900, letterSpacing: "-2px" }}>Browse free. Save smarter.</div><div style={{ marginTop: 18, fontSize: 30, fontWeight: 800 }}>dealledger.eu/us · Link in bio</div></div>
    </div>
  </AbsoluteFill>;
};

const ClearPriceLayout = () => {
  const frame = useCurrentFrame();
  const intro = eased(frame, 0, 20);
  const split = eased(frame, 92, 110);
  const clear = eased(frame, 240, 258);
  const close = eased(frame, 458, 478);
  const deal = demoDeals[0];
  return <AbsoluteFill style={frameStyle}>
    <div style={{ position: "absolute", inset: 88, display: "flex", flexDirection: "column" }}>
      <div style={{ opacity: intro }}><Brand /></div>
      <div style={{ opacity: intro, marginTop: 110, fontFamily: '"Iowan Old Style", "Palatino Linotype", serif', fontSize: 108, lineHeight: 0.92, letterSpacing: "-5px", fontWeight: 700 }}>Too many tabs.<br />Too little clarity.</div>
      <div style={{ opacity: split, display: "flex", gap: 26, marginTop: 72, flex: 1, maxHeight: 600 }}>
        <div style={{ flex: 1, borderRadius: 36, padding: 34, background: "#e6ddd0", color: "#684e3c" }}><div style={{ fontSize: 22, letterSpacing: "0.12em", fontWeight: 900 }}>THE ENDLESS SCROLL</div><div style={{ marginTop: 46, fontSize: 45, lineHeight: 1.05, fontWeight: 850 }}>Is this actually a good price?</div><div style={{ marginTop: 52, display: "grid", gap: 18 }}>{["Was $549.99?", "Prime only?", "Coupon needed?"].map((label) => <div key={label} style={{ padding: 18, borderRadius: 18, background: "rgba(255,253,249,.72)", fontSize: 27, fontWeight: 750 }}>?</div>)}</div></div>
        <div style={{ flex: 1, borderRadius: 36, padding: 28, background: "#17332e", color: "#fffdf9" }}><div style={{ color: "#f1c57a", fontSize: 22, letterSpacing: "0.12em", fontWeight: 900 }}>DEAL LEDGER</div><div style={{ marginTop: 28, borderRadius: 24, background: "#fffdf9", overflow: "hidden", isolation: "isolate" }}><div style={{ height: 255, position: "relative", zIndex: 1, overflow: "hidden", padding: 22, display: "grid", placeItems: "center", background: "#fffdf9" }}><Img src={staticFile(deal.imagePath)} style={{ position: "relative", zIndex: 1, display: "block", width: "100%", height: "100%", maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }} /></div><div style={{ position: "relative", zIndex: 2, padding: 22, color: "#fffdf9", background: "#17332e" }}><div style={{ color: "#d7e8df", fontSize: 14, fontWeight: 850, letterSpacing: "0.1em" }}>CURRENT PRICE</div><div style={{ marginTop: 3, fontSize: 41, fontWeight: 900, lineHeight: 1 }}>${deal.salePrice.toFixed(2)} <span style={{ color: "#f1c57a", fontSize: 24 }}>{Math.round(deal.discountPct * 100)}% OFF</span></div><div style={{ marginTop: 9, color: "#d7e8df", fontSize: 21, fontWeight: 800 }}>Reference: ${deal.listPrice.toFixed(2)}</div></div></div></div>
      </div>
      <div style={{ opacity: clear, position: "absolute", top: 1260, left: 88, right: 88, borderRadius: 32, padding: "28px 34px", background: "#fffdf9", boxShadow: "0 20px 50px rgba(29,43,36,.14)", fontSize: 34, fontWeight: 800 }}>Clear price context. Better decisions.</div>
      <div style={{ opacity: close, marginTop: "auto", color: "#136f63", fontSize: 48, fontWeight: 900, letterSpacing: "-2px" }}>Find what’s worth a closer look.</div>
      <div style={{ opacity: close, marginTop: 14, fontSize: 30, fontWeight: 800 }}>dealledger.eu/us · Link in bio</div>
    </div>
  </AbsoluteFill>;
};

const PersonalAlertsLayout = () => {
  const frame = useCurrentFrame();
  const intro = eased(frame, 0, 20);
  const panel = eased(frame, 110, 128);
  const close = eased(frame, 462, 482);
  return <AbsoluteFill style={frameStyle}>
    <div style={{ position: "absolute", inset: 88, display: "flex", flexDirection: "column" }}>
      <div style={{ opacity: intro }}><Brand /></div>
      <div style={{ opacity: intro, marginTop: 108, fontFamily: '"Iowan Old Style", "Palatino Linotype", serif', fontSize: 106, lineHeight: 0.92, letterSpacing: "-5px", fontWeight: 700 }}>Only see deals<br />you care about.</div>
      <div style={{ opacity: intro, marginTop: 34, color: "#486057", fontSize: 37, fontWeight: 650 }}>Choose categories. Or request an alert for a specific item.</div>
      <div style={{ opacity: panel, marginTop: 68, padding: 42, borderRadius: 42, background: "#fffdf9", boxShadow: "0 28px 65px rgba(29,43,36,.14)" }}>
        <div style={{ color: "#136f63", fontSize: 23, fontWeight: 900, letterSpacing: "0.13em" }}>WHAT DO YOU WANT TO TRACK?</div>
        <div style={{ display: "grid", gap: 16, marginTop: 30 }}><CheckRow index={0} label="Audio" /><CheckRow index={1} label="Home office" /><CheckRow index={2} label="Robot vacuums" /></div>
        <div style={{ opacity: eased(frame, 248, 266), marginTop: 26, padding: "23px 24px", borderRadius: 22, border: "3px solid #cbd9d1", color: "#63746a", fontSize: 28, fontWeight: 650 }}>Or add an exact item, model, or product link</div>
        <div style={{ opacity: eased(frame, 285, 303), marginTop: 24, padding: "24px 28px", borderRadius: 22, background: "#136f63", color: "#fffdf9", fontSize: 31, textAlign: "center", fontWeight: 900 }}>REQUEST FREE ALERTS</div>
      </div>
      <div style={{ opacity: close, marginTop: "auto" }}><div style={{ color: "#136f63", fontSize: 48, fontWeight: 900, letterSpacing: "-2px" }}>Your categories. Your timing.</div><div style={{ marginTop: 16, fontSize: 30, fontWeight: 800 }}>dealledger.eu/us · Link in bio</div></div>
    </div>
  </AbsoluteFill>;
};

export const DealLedgerExplainer: React.FC<{ variant: ExplainerVariant }> = ({ variant }) => {
  const { audio } = explainerVariants[variant];
  const { durationInFrames } = useVideoConfig();
  const fadeOut = interpolate(useCurrentFrame(), [durationInFrames - 12, durationInFrames], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const layout = variant === "save-time" ? <SaveTimeLayout /> : variant === "clear-price" ? <ClearPriceLayout /> : <PersonalAlertsLayout />;
  return <AbsoluteFill style={{ opacity: fadeOut }}><Audio src={staticFile(audio)} volume={0.9} />{layout}</AbsoluteFill>;
};
