export type Deal = {
  asin: string;
  title: string;
  shortTitle: string;
  family?: string;
  category?: string;
  salePrice: number;
  listPrice: number;
  discountPct: number;
  imagePath: string;
};

export type ReelData = {
  audioSegments: Array<{
    path: string;
    durationInFrames: number;
  }>;
  generatedAt: string;
  deals: Deal[];
};
