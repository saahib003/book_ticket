/** Small, framework-independent rules used by the booking screen. */

export function remainingHoldSeconds(expiresAt: string, now = Date.now()): number {
  return Math.max(0, Math.ceil((new Date(expiresAt).getTime() - now) / 1000));
}

export function canSelectAnotherSeat(selectedCount: number, maximum = 10): boolean {
  return selectedCount < maximum;
}
