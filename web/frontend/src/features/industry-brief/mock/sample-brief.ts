import type { IndustryBrief } from "../types";

// Phase 1: 정적 목업 데이터. 실제 수집/분석은 Phase 2 이후.
export const SAMPLE_BRIEF: IndustryBrief = {
  briefDate: "2026-08-10",
  generatedAt: "2026-08-10T07:00:00+09:00",
  periodLabel: "지난 24시간",
  articleCount: 183,

  game: {
    headline: "신작 발표보다 기존 게임의 라이브 서비스 강화와\n운영 효율화 움직임이 두드러지고 있습니다.",
    briefing: [
      "오늘 수집된 게임업계 자료를 종합하면, 신규 IP나 대작 발표보다 기존 서비스의 운영 효율화와 콘텐츠 주기 최적화에 초점이 맞춰져 있습니다. 여러 퍼블리셔가 라이브 서비스 게임의 시즌 콘텐츠 제작 주기를 단축하는 내부 도구 도입을 언급했습니다.",
      "스팀 플랫폼에서는 여름 세일 이후 트래픽 흐름을 분석한 자료가 다수 등장했고, 중소 개발사들의 '롱테일 생존 전략'이 반복적으로 언급되는 주제였습니다.",
      "한편 대형 퍼블리셔 중 한 곳은 신규 스튜디오 인수보다 기존 IP의 플랫폼 확장(콘솔·모바일 동시 출시)에 투자를 집중하겠다고 공식 발표했습니다.",
    ],
    changes: [
      { direction: "up", topic: "라이브 서비스 운영 효율화", description: "시즌 콘텐츠 제작 주기 단축 관련 도구·사례 언급이 전일 대비 크게 늘었습니다." },
      { direction: "flat", topic: "콘솔 신작 발표", description: "관심은 꾸준하지만 전일 대비 특별한 증가는 없습니다." },
      { direction: "down", topic: "Web3 게임", description: "최근 7일 평균과 비교해 주요 발표와 보도가 감소했습니다." },
    ],
    watchList: [
      { rank: 1, topic: "시즌제 콘텐츠 자동화 도구", description: "라이브 서비스 게임사들이 실제 도입 사례를 공개하는지 지켜볼 필요가 있습니다." },
      { rank: 2, topic: "스팀 롱테일 전략 확산", description: "중소 개발사 사례가 대형 퍼블리셔로도 확산되는지 주목합니다." },
    ],
  },

  ai: {
    headline: "AI 경쟁의 중심이 새로운 모델 발표에서\n실제 업무 자동화와 서비스 적용으로 이동하고 있습니다.",
    briefing: [
      "오늘의 AI 업계 자료는 신규 모델 출시 소식보다 기존 모델을 활용한 업무 자동화 사례에 집중돼 있습니다. 특히 코드 생성을 넘어 실제 개발 작업 전반을 수행하는 'Agent' 형태의 제품 발표가 여러 건 확인됩니다.",
      "주요 기업들의 공식 발표에서는 이미지·영상 생성보다 기업 도입 사례와 비용 효율성을 강조하는 톤이 두드러졌고, 검색·리서치 영역에서도 에이전트 기반 접근이 반복적으로 등장했습니다.",
      "규제 관련해서는 특별히 새로운 흐름 없이 기존 논의가 유지되는 수준이었습니다.",
    ],
    changes: [
      { direction: "up", topic: "AI Coding Agent", description: "신규 모델 자체보다 개발 자동화 관련 발표와 서비스 업데이트가 크게 증가했습니다." },
      { direction: "up", topic: "기업 도입 사례", description: "실제 업무에 AI를 적용한 사례 보도가 늘었습니다." },
      { direction: "flat", topic: "이미지·영상 생성", description: "관심은 유지되고 있지만 눈에 띄는 변화는 없습니다." },
    ],
    watchList: [
      { rank: 1, topic: "AI Coding Agent", description: "코드 생성에서 실제 개발 업무 수행까지 Agent의 역할이 확대되는지 확인할 필요가 있습니다." },
      { rank: 2, topic: "AI 비용 구조 변화", description: "기업 도입이 늘면서 비용 관련 논의가 어떻게 바뀌는지 지켜봅니다." },
    ],
  },

  crossInsight: {
    hasSignal: true,
    summary: [
      "게임업계의 AI 적용 중심이 소비자 노출 기능보다 제작 생산성과 운영 자동화로 이동하고 있습니다.",
      "관련 자료를 종합하면 AI NPC나 생성형 콘텐츠보다 코딩, QA, 번역, 아트 제작 보조, 운영 분석에 대한 실제 적용 사례가 더 빠르게 증가하고 있습니다.",
    ],
    opinion:
      "제작 파이프라인에 이미 AI 도구를 내재화한 스튜디오는 콘텐츠 생산 속도에서 우위를 가져갈 가능성이 큰 반면, 외주 아트·QA 비중이 높은 소규모 스튜디오는 비용 구조 재편 압박을 받을 것으로 보입니다. 다음 분기 실적 발표에서 인건비 대비 콘텐츠 산출량 지표나 AI 툴 라이선스 관련 투자 공시가 나오는지가 이 흐름이 굳어지는지 판단할 단서가 될 것입니다.",
  },

  signals: [
    { topic: "AI Agent", direction: "up", weight: 92, kind: "INDUSTRY", kindLabel: "산업 주제", state: "NEW", stateLabel: "새로 등장", todayCount: 8, baselineAverage: 0, sourceCount: 5, reason: "직전 7일에는 없던 키워드가 최근 24시간에 8건 포착됐습니다.", evidence: [] },
    { topic: "Live Service", direction: "up", weight: 78, kind: "INDUSTRY", kindLabel: "산업 주제", state: "EXPANDING", stateLabel: "확산 중", todayCount: 6, baselineAverage: 2.1, sourceCount: 4, reason: "최근 24시간 6건으로, 직전 7일 일평균 2.1건보다 늘었습니다.", evidence: [] },
    { topic: "AI Coding", direction: "up", weight: 71, kind: "INDUSTRY", kindLabel: "산업 주제", state: "GROWING", stateLabel: "증가 중", todayCount: 5, baselineAverage: 2.4, sourceCount: 3, reason: "최근 24시간 5건이 관찰됐습니다.", evidence: [] },
    { topic: "Steam", direction: "flat", weight: 54, kind: "INDUSTRY", kindLabel: "산업 주제", state: "CONTINUING", stateLabel: "지속 관찰", todayCount: 4, baselineAverage: 4, sourceCount: 2, reason: "최근 24시간 4건으로 기존 흐름이 이어집니다.", evidence: [] },
    { topic: "Web3", direction: "down", weight: 21, kind: "INDUSTRY", kindLabel: "산업 주제", state: "DECLINING", stateLabel: "약화 중", todayCount: 1, baselineAverage: 3, sourceCount: 1, reason: "최근 언급량이 기준선보다 줄었습니다.", evidence: [] },
  ],

  newToday: [
    {
      topic: "AI Browser",
      description: "오늘 관련 발표와 보도가 처음 크게 증가했습니다.",
      articleCount: 14,
      independentSources: 8,
      officialCount: 2,
    },
  ],

  issues: [
    {
      id: "issue-ai-coding-agent",
      category: "AI",
      importance: "높음",
      title: "AI Coding Agent 경쟁 확대",
      summary: "여러 AI 기업이 단순 코드 추천을 넘어 실제 개발 작업을 수행하는 Agent 기능을 강화하고 있습니다.",
      whyItMatters: "AI 개발도구의 경쟁 기준이 코드 생성 품질에서 업무 수행 능력으로 이동하고 있습니다.",
      lifecycle: "GROWING",
      relatedBriefing: "AI INDUSTRY / AI Coding 분석",
      confidence: { level: "STRONG", articleCount: 11, independentSources: 7, officialCount: 2 },
      sources: [
        { outlet: "OpenAI 공식", title: "새로운 코딩 에이전트 업데이트 공개", publishedAgo: "2시간 전", url: "#" },
        { outlet: "TechCrunch", title: "AI 코딩 에이전트, 코드 리뷰까지 자동화", publishedAgo: "3시간 전", url: "#" },
        { outlet: "The Verge", title: "개발자들이 말하는 AI 에이전트의 실제 생산성", publishedAgo: "4시간 전", url: "#" },
      ],
    },
    {
      id: "issue-live-service-ops",
      category: "GAME",
      importance: "높음",
      title: "라이브 서비스 게임 운영 자동화 확산",
      summary: "시즌 콘텐츠 제작·배포 주기를 단축하는 내부 파이프라인 도입 사례가 늘고 있습니다.",
      whyItMatters: "콘텐츠 제작 비용과 속도가 라이브 서비스 게임의 핵심 경쟁력으로 다시 부각되고 있습니다.",
      lifecycle: "GROWING",
      relatedBriefing: "GAME INDUSTRY / 라이브 서비스 운영 효율화",
      confidence: { level: "STRONG", articleCount: 9, independentSources: 6, officialCount: 1 },
      sources: [
        { outlet: "게임메카", title: "시즌 콘텐츠 제작 주기, 절반으로 줄인 사례", publishedAgo: "5시간 전", url: "#" },
        { outlet: "GamesIndustry.biz", title: "Live-ops teams turn to internal automation", publishedAgo: "6시간 전", url: "#" },
      ],
    },
    {
      id: "issue-ai-browser",
      category: "AI",
      importance: "보통",
      title: "AI 브라우저 신규 등장",
      summary: "브라우징 자체를 에이전트가 대신 수행하는 형태의 제품 발표가 오늘 처음 눈에 띄게 늘었습니다.",
      whyItMatters: "검색·리서치 UX의 다음 경쟁 지점이 브라우저 레벨로 이동할 가능성을 보여줍니다.",
      lifecycle: "EMERGING",
      relatedBriefing: "AI INDUSTRY / 검색",
      confidence: { level: "MODERATE", articleCount: 14, independentSources: 8, officialCount: 2 },
      sources: [
        { outlet: "Ars Technica", title: "AI 브라우저 경쟁, 오늘 본격 시작되다", publishedAgo: "1시간 전", url: "#" },
        { outlet: "The Verge", title: "새로운 AI 브라우저 3종 비교", publishedAgo: "3시간 전", url: "#" },
      ],
    },
    {
      id: "issue-web3-decline",
      category: "GAME",
      importance: "보통",
      title: "Web3 게임 발표 감소 지속",
      summary: "최근 7일 평균 대비 Web3 관련 신규 발표와 보도가 눈에 띄게 줄었습니다.",
      whyItMatters: "업계 투자·개발 관심이 다른 영역(라이브 서비스, AI 도구)으로 이동하고 있음을 시사합니다.",
      lifecycle: "DECLINING",
      relatedBriefing: "GAME INDUSTRY / Today Changed",
      confidence: { level: "MODERATE", articleCount: 4, independentSources: 3, officialCount: 0 },
      sources: [
        { outlet: "게임조선", title: "Web3 게임 신작 소식, 올해 최저치", publishedAgo: "8시간 전", url: "#" },
      ],
    },
  ],
};
