import { useEffect, useState } from "react";
import type { IndustryBrief } from "../types";
import { LeadCard } from "./LeadCard";

interface Slide {
  key: string;
  categoryLabel: string;
  color: string;
  headline: string;
  grounds: Array<{ label: string; body: string }>;
}

const ROTATE_MS = 7000;

type CategoryBrief = { headline: string; keySummaries?: string[]; watchList: Array<{ topic: string }> };

/** 근거 1/2 + 지켜볼 것 3칸을 채운다. 지켜볼 것이 이미 watchList[0]을 쓰므로,
 * 근거 2가 keySummaries[1]로 못 채워질 때는 watchList[1]로 대체해 같은 문장이
 * 두 칸에 중복 노출되는 걸 피한다(핵심 이슈 후보가 오늘 1개뿐인 카테고리에서
 * 실제로 발생했던 문제). watchList도 1개뿐이면 그때는 어쩔 수 없이 안내
 * 문구로 채운다. */
function buildGrounds(category: CategoryBrief): Array<{ label: string; body: string }> {
  return [
    { label: "근거 1", body: category.keySummaries?.[0] ?? category.headline },
    {
      label: "근거 2",
      body: category.keySummaries?.[1] ?? category.watchList[1]?.topic ?? "추가로 확인된 근거가 없습니다.",
    },
    { label: "지켜볼 것", body: category.watchList[0]?.topic ?? "아직 특별히 지켜볼 항목이 없습니다." },
  ];
}

/** 업계동향 탭 리드 카드 — 게임/AI를 한 문장으로 억지로 합치면
 * ("...공개했다.와 교차 확인된 핵심 이슈가 아직 없습니다." 같은) 말이
 * 안 되는 조합이 나온다. 대신 게임/AI/게임×AI를 각각 독립된 슬라이드로
 * 두고 돌아가며 보여준다 — 판단할 이슈가 없는 카테고리는 슬라이드
 * 자체를 건너뛴다. */
export function TodayLeadCard({ brief }: { brief: IndustryBrief }) {
  const slides: Slide[] = [];
  if (brief.game.hasSignal) {
    slides.push({
      key: "game",
      categoryLabel: "GAME",
      color: "var(--cat-game)",
      headline: brief.game.headline,
      grounds: buildGrounds(brief.game),
    });
  }
  if (brief.ai.hasSignal) {
    slides.push({
      key: "ai",
      categoryLabel: "AI",
      color: "var(--cat-ai)",
      headline: brief.ai.headline,
      grounds: buildGrounds(brief.ai),
    });
  }
  if (brief.crossInsight.hasSignal) {
    slides.push({
      key: "cross",
      categoryLabel: "GAME×AI",
      color: "var(--success)",
      headline: brief.crossInsight.summary[0],
      grounds: [
        { label: "근거 1", body: brief.game.headline },
        { label: "근거 2", body: brief.ai.headline },
        { label: "지켜볼 것", body: brief.crossInsight.opinion },
      ],
    });
  }

  const [index, setIndex] = useState(0);
  useEffect(() => {
    setIndex(0);
  }, [slides.length]);
  useEffect(() => {
    if (slides.length <= 1) return;
    const timer = window.setInterval(() => setIndex((current) => (current + 1) % slides.length), ROTATE_MS);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slides.length]);

  if (slides.length === 0) return null;
  const slide = slides[index % slides.length];

  return (
    <div className="ib-lead-flap" key={slide.key}>
      <LeadCard
        dotColor="var(--success)"
        eyebrow="오늘의 판단"
        categoryBadge={{ label: slide.categoryLabel, color: slide.color }}
        headline={slide.headline}
        clamped
        grounds={slide.grounds}
      />
    </div>
  );
}
