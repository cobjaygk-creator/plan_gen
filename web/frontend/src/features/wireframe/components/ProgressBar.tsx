interface Props {
  value: number;
  label: string;
  caption: string;
}

export function ProgressBar({ value, label, caption }: Props) {
  const percent = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div className="wf-progress">
      <div
        className="wf-progress-track"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
      >
        <span className="wf-progress-fill" style={{ width: `${percent}%` }} />
      </div>
      <span className="wf-progress-caption">
        {caption} · {percent}%
      </span>
    </div>
  );
}
