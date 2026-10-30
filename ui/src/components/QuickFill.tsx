// One-click examples beside a field, for a demo without typing. Picking one fills the field; the
// person still presses the real button, so every entry goes through the usual path.

import { Icon } from './viz';

export type Pick = { label: string; title?: string; onPick: () => void };

export function QuickFill({ picks, label = 'Quick fill' }: { picks: Pick[]; label?: string }) {
  if (picks.length === 0) return null;
  return (
    <div className="quick-fill">
      <span className="quick-k"><Icon name="bolt" size={14} />{label}</span>
      {picks.map((p) => (
        <button key={p.label} type="button" className="quick-btn" title={p.title} onClick={p.onPick}>{p.label}</button>
      ))}
    </div>
  );
}
