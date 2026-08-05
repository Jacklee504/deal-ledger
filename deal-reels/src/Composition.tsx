import { Composition } from "remotion";
import { DealLedgerReel } from "./DealLedgerReel";
import reelData from "./data/reel.json";
import { CoverScene } from "./scenes/CoverScene";
import { DealLedgerExplainer } from "./ExplainerReel";
import { DealLedgerSlideshow, slideshowDurationInFrames } from "./DealLedgerSlideshow";
import type { ReelData } from "./types";

const reel = reelData as ReelData;
const durationInFrames = reel.audioSegments.reduce((total, segment) => total + segment.durationInFrames, 0);

export const DealLedgerComposition = () => {
  return (
    <>
      <Composition
        id="DealLedgerReel"
        component={DealLedgerReel}
        durationInFrames={durationInFrames}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="DealLedgerSlideshow"
        component={DealLedgerSlideshow}
        durationInFrames={slideshowDurationInFrames}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="DealLedgerCover"
        component={() => <CoverScene deals={reel.deals} />}
        durationInFrames={1}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="DealLedgerInstagramCover"
        component={() => <CoverScene deals={reel.deals} social />}
        durationInFrames={1}
        fps={30}
        width={1080}
        height={1440}
      />
      <Composition id="DealLedgerExplainerSaveTime" component={() => <DealLedgerExplainer variant="save-time" />} durationInFrames={600} fps={30} width={1080} height={1920} />
      <Composition id="DealLedgerExplainerClearPrice" component={() => <DealLedgerExplainer variant="clear-price" />} durationInFrames={600} fps={30} width={1080} height={1920} />
      <Composition id="DealLedgerExplainerPersonalAlerts" component={() => <DealLedgerExplainer variant="personal-alerts" />} durationInFrames={600} fps={30} width={1080} height={1920} />
    </>
  );
};
