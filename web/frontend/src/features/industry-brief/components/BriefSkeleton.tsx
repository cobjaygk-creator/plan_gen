/** 로딩 스켈레톤 (design_handoff 6단계 신설) — 최종 레이아웃(리드 카드)과
 * 같은 골격의 회색 블록. 이전엔 "불러오는 중입니다" 텍스트 한 줄뿐이라
 * 완료 시 레이아웃이 통째로 나타나며 화면이 크게 점프했다. */
export function BriefSkeleton() {
  return (
    <div className="ib-page-bg">
      <div className="ib-stack">
        <div className="ib-skel ib-skel-page-title" />
        <div className="ib-skel-card">
          <div className="ib-skel ib-skel-eyebrow" />
          <div className="ib-skel ib-skel-line" style={{ width: "78%" }} />
          <div className="ib-skel ib-skel-line" style={{ width: "52%" }} />
          <div className="ib-skel-divider" />
          <div className="ib-skel-grounds">
            {[0, 1, 2].map((index) => (
              <div className="ib-skel-ground" key={index}>
                <div className="ib-skel ib-skel-label" />
                <div className="ib-skel ib-skel-line" />
                <div className="ib-skel ib-skel-line" style={{ width: "70%" }} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
