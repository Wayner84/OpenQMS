import { describe, expect, it, vi } from 'vitest';

import { emitUnauthorized, onUnauthorized } from './sessionEvents';

describe('sessionEvents', () => {
  it('notifies every subscriber on emit', () => {
    const first = vi.fn();
    const second = vi.fn();
    onUnauthorized(first);
    onUnauthorized(second);

    emitUnauthorized();

    expect(first).toHaveBeenCalledOnce();
    expect(second).toHaveBeenCalledOnce();
  });

  it('stops notifying a listener once unsubscribed', () => {
    const listener = vi.fn();
    const unsubscribe = onUnauthorized(listener);

    unsubscribe();
    emitUnauthorized();

    expect(listener).not.toHaveBeenCalled();
  });
});
