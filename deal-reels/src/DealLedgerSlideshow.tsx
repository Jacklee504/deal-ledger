import { AbsoluteFill, Sequence } from "remotion";
import reelData from "./data/reel.json";
import { SlideshowCtaScene } from "./scenes/SlideshowCtaScene";
import { SlideshowDealScene } from "./scenes/SlideshowDealScene";
import { SlideshowHookScene } from "./scenes/SlideshowHookScene";
import type { ReelData } from "./types";

const reel = reelData as ReelData;
const hookFrames = 60;
const dealFrames = 60;
const ctaFrames = 60;

export const slideshowDurationInFrames = hookFrames + reel.deals.length * dealFrames + ctaFrames;

export const DealLedgerSlideshow: React.FC = () => (
  <AbsoluteFill>
    <Sequence durationInFrames={hookFrames} layout="none"><SlideshowHookScene deals={reel.deals} /></Sequence>
    {reel.deals.map((deal, index) => (
      <Sequence key={deal.asin} from={hookFrames + index * dealFrames} durationInFrames={dealFrames} layout="none">
        <SlideshowDealScene deal={deal} rank={index + 1} durationInFrames={dealFrames} />
      </Sequence>
    ))}
    <Sequence from={hookFrames + reel.deals.length * dealFrames} durationInFrames={ctaFrames} layout="none"><SlideshowCtaScene /></Sequence>
  </AbsoluteFill>
);
