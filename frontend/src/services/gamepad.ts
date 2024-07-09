class GamepadService {
  private gamepads: { [index: number]: Gamepad } = {};
  private pressedButtons: Set<number> = new Set();

  constructor() {
    this.startPolling();
  }

  private startPolling(): void {
    window.addEventListener("gamepadconnected", (event: GamepadEvent) => {
      console.log("Gamepad connected:", event.gamepad);
      this.gamepads[event.gamepad.index] = event.gamepad;
      this.updateScrollState();
    });

    window.addEventListener("gamepaddisconnected", (event: GamepadEvent) => {
      console.log("Gamepad disconnected:", event.gamepad);
      delete this.gamepads[event.gamepad.index];
      this.updateScrollState();
    });

    this.pollGamepads();
  }

  private pollGamepads(): void {
    const gamepads = navigator.getGamepads();
    for (const gamepad of gamepads) {
      if (gamepad) {
        this.gamepads[gamepad.index] = gamepad;
      }
    }
    this.handleButtonPress();
    requestAnimationFrame(this.pollGamepads.bind(this));
  }

  private updateScrollState(): void {
    if (Object.keys(this.gamepads).length > 0) {
      document.body.classList.add("no-scroll");
    } else {
      document.body.classList.remove("no-scroll");
    }
  }

  public getGamepads(): { [index: number]: Gamepad } {
    return this.gamepads;
  }

  public handleButtonPress(): void {
    for (const gamepad of Object.values(this.gamepads)) {
      gamepad.buttons.forEach((button, index) => {
        if (button.pressed && !this.pressedButtons.has(index)) {
          this.pressedButtons.add(index);
          console.log(`Button ${index} pressed`);
          this.performAction(index);
        } else if (!button.pressed && this.pressedButtons.has(index)) {
          this.pressedButtons.delete(index);
        }
      });
    }
  }

  private performAction(buttonIndex: number): void {
    // Prevent default actions based on button index
    switch (buttonIndex) {
      case 0: // A button
        break;
      case 1: // B button
        break;
      case 2: // X button
        break;
      case 3: // Y button
        break;
      case 12: // D-Pad Up
        break;
      case 13: // D-Pad Down
        break;
      case 14: // D-Pad Left
        break;
      case 15: // D-Pad Right
        break;
      default:
        console.log(`Button ${buttonIndex} pressed`);
        break;
    }
  }
}

export default new GamepadService();
