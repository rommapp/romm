const noHaptics: GamepadHapticActuator = {
  playEffect: () => Promise.resolve("complete"),
  reset: () => Promise.resolve("complete"),
};

/** The standard mapping's 17 buttons, with the given indices held. */
export function buttonsHolding(...held: number[]): GamepadButton[] {
  return Array.from({ length: 17 }, (_, i) => ({
    pressed: held.includes(i),
    touched: held.includes(i),
    value: held.includes(i) ? 1 : 0,
  }));
}

export function gamepadFixture(overrides: Partial<Gamepad> = {}): Gamepad {
  return {
    index: 0,
    id: "test-pad",
    connected: true,
    mapping: "standard",
    axes: [0, 0, 0, 0],
    buttons: buttonsHolding(),
    timestamp: 0,
    vibrationActuator: noHaptics,
    ...overrides,
  };
}
