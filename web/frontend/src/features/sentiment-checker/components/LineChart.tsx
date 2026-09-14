interface Point {
  label: string;
  value: number;
}

interface LineChartProps {
  points: Point[];
  height?: number;
  color?: string;
  /** 자동 계산 대신 y축 하한을 0으로 고정(민심 지수처럼 0~100 스케일일 때). */
  yMin?: number;
  yMax?: number;
  valueFormatter?: (value: number) => string;
  emptyText?: string;
}

const WIDTH = 640;

/** 별도 차트 라이브러리 없이 direct SVG로 그리는 얇은 라인+면적 차트.
 * 민심 점수 추이(대시보드)와 이슈별 일자 언급 추이(상세 모달) 양쪽에서
 * 재사용한다 — 예전엔 각각 div 높이를 밀어올리는 막대 흉내로 따로
 * 그려져 있었다. */
export function LineChart({ points, height = 140, color = "var(--accent)", yMin, yMax, valueFormatter, emptyText = "데이터가 아직 없습니다." }: LineChartProps) {
  if (points.length === 0) {
    return <p className="sc-empty">{emptyText}</p>;
  }
  const values = points.map((p) => p.value);
  const min = yMin ?? Math.min(...values);
  const max = yMax ?? Math.max(...values);
  const span = Math.max(1e-6, max - min);
  const padTop = 18;
  const padBottom = 22;
  const plotHeight = height - padTop - padBottom;
  const stepX = points.length > 1 ? WIDTH / (points.length - 1) : 0;

  const coords = points.map((p, i) => {
    const x = points.length > 1 ? i * stepX : WIDTH / 2;
    const ratio = (p.value - min) / span;
    const y = padTop + (1 - ratio) * plotHeight;
    return { x, y, point: p };
  });

  const linePath = coords.map((c, i) => `${i === 0 ? "M" : "L"}${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(" ");
  const areaPath = `${linePath} L${coords[coords.length - 1].x.toFixed(1)},${(padTop + plotHeight).toFixed(1)} L${coords[0].x.toFixed(1)},${(padTop + plotHeight).toFixed(1)} Z`;

  // 라벨이 다 겹치지 않도록 최대 6개까지만 골라서 보여준다.
  const labelStep = Math.max(1, Math.ceil(coords.length / 6));
  const last = coords[coords.length - 1];

  return (
    <svg className="sc-linechart" viewBox={`0 0 ${WIDTH} ${height}`} preserveAspectRatio="none" role="img">
      <line x1="0" y1={padTop + plotHeight} x2={WIDTH} y2={padTop + plotHeight} className="sc-linechart-baseline" />
      <path d={areaPath} fill={color} opacity="0.12" stroke="none" />
      <path d={linePath} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={last.x} cy={last.y} r="3.5" fill={color} />
      {coords.map((c, i) =>
        i % labelStep === 0 || i === coords.length - 1 ? (
          <text key={i} x={Math.min(Math.max(c.x, 14), WIDTH - 14)} y={height - 4} textAnchor="middle" className="sc-linechart-label">
            {c.point.label}
          </text>
        ) : null
      )}
      <text x={last.x} y={last.y - 10} textAnchor={last.x > WIDTH - 40 ? "end" : "middle"} className="sc-linechart-endpoint">
        {valueFormatter ? valueFormatter(last.point.value) : last.point.value}
      </text>
    </svg>
  );
}
