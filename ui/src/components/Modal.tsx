// A dialog over the page: Esc or the close button dismisses it, focus moves into it and comes
// back when it closes. Square, flat, one shadow because it floats.

import { useEffect, useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { Icon } from './viz';
import type { Tone } from './Toast';

export function Modal({ title, kicker, tone = 'turn', onClose, children, footer, wide = false }: {
  title: ReactNode; kicker?: ReactNode; tone?: Tone; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean;
}) {
  const id = useId();
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const back = document.activeElement as HTMLElement | null;
    const first = box.current?.querySelector<HTMLElement>('input, select, textarea, button:not(.modal-x)');
    (first ?? box.current)?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    document.body.classList.add('modal-open');
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.classList.remove('modal-open');
      back?.focus();
    };
  }, [onClose]);

  return createPortal(
    <div className="modal-scrim" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div ref={box} className={`modal tone-${tone}${wide ? ' modal-wide' : ''}`} role="dialog" aria-modal="true" aria-labelledby={id} tabIndex={-1}>
        <header className="modal-head">
          <div>
            {kicker && <p className="modal-kicker">{kicker}</p>}
            <h2 id={id} className="section">{title}</h2>
          </div>
          <button type="button" className="modal-x" aria-label="Close" onClick={onClose}><Icon name="x" size={16} /></button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-foot">{footer}</footer>}
      </div>
    </div>,
    document.body,
  );
}
