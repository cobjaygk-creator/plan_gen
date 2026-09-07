interface EmptyStateAction {
  label: string;
  onClick: () => void;
  variant?: "primary" | "ghost";
}

/** 4개 탭 공통 빈 상태(design_handoff 6단계 신설) — "핵심 이슈로 뽑을 만큼
 * 기사가 모이지 않았습니다" 한 줄 대신, 날짜·이유를 구체적으로 밝히고
 * 다음 행동(가장 최근 브리핑 보기 등)까지 안내한다. */
export function EmptyState({ title, description, actions }: { title: string; description: string; actions?: EmptyStateAction[] }) {
  return (
    <div className="ib-empty-state">
      <div className="ib-empty-state-icon" aria-hidden="true">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="7" />
          <line x1="21" y1="21" x2="16.5" y2="16.5" />
        </svg>
      </div>
      <div className="ib-empty-state-body">
        <p className="ib-empty-state-title">{title}</p>
        <p className="ib-empty-state-desc">{description}</p>
        {actions && actions.length > 0 && (
          <div className="ib-empty-state-actions">
            {actions.map((action) => (
              <button
                key={action.label}
                type="button"
                className={`ib-empty-state-action${action.variant === "ghost" ? " is-ghost" : ""}`}
                onClick={action.onClick}
              >
                {action.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
