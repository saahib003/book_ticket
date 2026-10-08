import { describe, expect, it } from "vitest";
import { canSelectAnotherSeat, remainingHoldSeconds } from "./bookingState";

describe("booking state rules", () => {
  it("counts a hold down and rounds partial seconds up", () => {
    const now = Date.parse("2026-09-02T10:00:00.000Z");
    expect(remainingHoldSeconds("2026-09-02T10:00:05.100Z", now)).toBe(6);
  });

  it("never returns a negative countdown after expiry", () => {
    const now = Date.parse("2026-09-02T10:00:10.000Z");
    expect(remainingHoldSeconds("2026-09-02T10:00:05.000Z", now)).toBe(0);
  });

  it("enforces the maximum ten seats per hold", () => {
    expect(canSelectAnotherSeat(9)).toBe(true);
    expect(canSelectAnotherSeat(10)).toBe(false);
  });
});
