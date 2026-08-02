import { AbsoluteFill, Audio, Sequence, staticFile } from "remotion";
import reelData from "./data/reel.json";
import { DealScene } from "./scenes/DealScene";
import { IntroScene } from "./scenes/IntroScene";
import { OverviewScene } from "./scenes/OverviewScene";
import { OutroScene } from "./scenes/OutroScene";
import type { ReelData } from "./types";

const reel = reelData as ReelData;

export const DealLedgerReel: React.FC = () => {
  const [intro, ...remainingAudio] = reel.audioSegments;
  const dealAudio = remainingAudio.slice(0, reel.deals.length);
  const [overview, outro] = remainingAudio.slice(reel.deals.length);
  let frame = 0;

  const timedScene = (durationInFrames: number, child: React.ReactNode) => {
    const from = frame;
    frame += durationInFrames;
    return (
      <Sequence from={from} durationInFrames={durationInFrames} layout="none">
        {child}
      </Sequence>
    );
  };

  return (
    <AbsoluteFill>
      {timedScene(
        intro.durationInFrames,
        <><Audio src={staticFile(intro.path)} volume={0.9} /><IntroScene /></>,
      )}
      {reel.deals.map((deal, index) =>
        timedScene(
          dealAudio[index].durationInFrames,
          <><Audio src={staticFile(dealAudio[index].path)} volume={0.9} /><DealScene deal={deal} rank={index + 1} durationInFrames={dealAudio[index].durationInFrames} /></>,
        ),
      )}
      {timedScene(
        overview.durationInFrames,
        <><Audio src={staticFile(overview.path)} volume={0.9} /><OverviewScene /></>,
      )}
      {timedScene(
        outro.durationInFrames,
        <><Audio src={staticFile(outro.path)} volume={0.9} /><OutroScene /></>,
      )}
    </AbsoluteFill>
  );
};
