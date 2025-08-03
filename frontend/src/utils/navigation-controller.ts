import { ref } from "vue";
import { useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import storeNavigation from "@/stores/navigation";
import storePlatforms from "@/stores/platforms";
import storeCollections from "@/stores/collections";

export interface NavigationElement {
  id: string;
  element: HTMLElement;
  priority: number;
  route?: string;
  action?: () => void;
  disabled?: boolean;
}

export interface GamepadState {
  connected: boolean;
  buttons: boolean[];
  axes: number[];
  lastPressed: string | null;
  deadzone: number;
}

export interface KeyboardState {
  keys: Set<string>;
  lastPressed: string | null;
}

class NavigationController {
  private router = useRouter();
  private navigationStore = storeNavigation();
  private platformsStore = storePlatforms();
  private collectionsStore = storeCollections();

  private elements = ref<NavigationElement[]>([]);
  private currentFocusIndex = ref(0);
  private isEnabled = ref(true);
  private gamepadState = ref<GamepadState>({
    connected: false,
    buttons: [],
    axes: [],
    lastPressed: null,
    deadzone: 0.5,
  });
  private keyboardState = ref<KeyboardState>({
    keys: new Set(),
    lastPressed: null,
  });

  // Navigation patterns
  private navigationPatterns = {
    horizontal: ["ArrowLeft", "ArrowRight", "KeyA", "KeyD"],
    vertical: ["ArrowUp", "ArrowDown", "KeyW", "KeyS"],
    confirm: ["Enter", "Space", "KeyZ"],
    back: ["Escape", "Backspace", "KeyX"],
    menu: ["Tab", "KeyM"],
    quickActions: {
      home: ["KeyH"],
      search: ["KeyF"],
      scan: ["KeyR"],
      platforms: ["KeyP"],
      collections: ["KeyC"],
    },
  };

  constructor() {
    this.setupEventListeners();
    this.setupGamepadPolling();
  }

  private setupEventListeners() {
    // Keyboard events
    document.addEventListener("keydown", this.handleKeyDown.bind(this));
    document.addEventListener("keyup", this.handleKeyUp.bind(this));

    // Gamepad events
    window.addEventListener(
      "gamepadconnected",
      this.handleGamepadConnected.bind(this),
    );
    window.addEventListener(
      "gamepaddisconnected",
      this.handleGamepadDisconnected.bind(this),
    );

    // Focus management
    document.addEventListener("focusin", this.handleFocusIn.bind(this));
    document.addEventListener("focusout", this.handleFocusOut.bind(this));
  }

  private setupGamepadPolling() {
    const pollGamepad = () => {
      if (this.gamepadState.value.connected) {
        const gamepads = navigator.getGamepads();
        const gamepad = gamepads[0]; // Use first connected gamepad

        if (gamepad) {
          this.gamepadState.value.buttons = gamepad.buttons.map(
            (btn) => btn.pressed,
          );
          this.gamepadState.value.axes = gamepad.axes;
          this.handleGamepadInput();
        }
      }
      requestAnimationFrame(pollGamepad);
    };

    pollGamepad();
  }

  private handleGamepadConnected(event: GamepadEvent) {
    this.gamepadState.value.connected = true;
    console.log("Gamepad connected:", event.gamepad.id);
  }

  private handleGamepadDisconnected(event: GamepadEvent) {
    this.gamepadState.value.connected = false;
    console.log("Gamepad disconnected:", event.gamepad.id);
  }

  private handleGamepadInput() {
    const { buttons, axes, deadzone } = this.gamepadState.value;

    // D-pad or left stick navigation
    const horizontalAxis = axes[0] || 0;
    const verticalAxis = axes[1] || 0;

    if (Math.abs(horizontalAxis) > deadzone) {
      if (horizontalAxis > 0) {
        this.navigate("right");
      } else {
        this.navigate("left");
      }
    }

    if (Math.abs(verticalAxis) > deadzone) {
      if (verticalAxis > 0) {
        this.navigate("down");
      } else {
        this.navigate("up");
      }
    }

    // Button actions
    if (buttons[0]?.pressed) {
      // A button
      this.activate();
    } else if (buttons[1]?.pressed) {
      // B button
      this.goBack();
    } else if (buttons[3]?.pressed) {
      // Y button
      this.openMenu();
    } else if (buttons[9]?.pressed) {
      // Start button
      this.togglePause();
    }
  }

  private handleKeyDown(event: KeyboardEvent) {
    if (!this.isEnabled.value) return;

    const key = event.code;
    this.keyboardState.value.keys.add(key);

    // Prevent default behavior for navigation keys
    if (
      this.navigationPatterns.horizontal.includes(key) ||
      this.navigationPatterns.vertical.includes(key) ||
      this.navigationPatterns.confirm.includes(key) ||
      this.navigationPatterns.back.includes(key)
    ) {
      event.preventDefault();
    }

    // Handle quick actions
    if (this.keyboardState.value.keys.has("KeyH")) {
      this.goHome();
    } else if (this.keyboardState.value.keys.has("KeyF")) {
      this.goSearch();
    } else if (this.keyboardState.value.keys.has("KeyR")) {
      this.goScan();
    } else if (this.keyboardState.value.keys.has("KeyP")) {
      this.openPlatforms();
    } else if (this.keyboardState.value.keys.has("KeyC")) {
      this.openCollections();
    }

    // Handle navigation
    if (this.navigationPatterns.horizontal.includes(key)) {
      if (key === "ArrowLeft" || key === "KeyA") {
        this.navigate("left");
      } else {
        this.navigate("right");
      }
    } else if (this.navigationPatterns.vertical.includes(key)) {
      if (key === "ArrowUp" || key === "KeyW") {
        this.navigate("up");
      } else {
        this.navigate("down");
      }
    } else if (this.navigationPatterns.confirm.includes(key)) {
      this.activate();
    } else if (this.navigationPatterns.back.includes(key)) {
      this.goBack();
    } else if (this.navigationPatterns.menu.includes(key)) {
      this.openMenu();
    }
  }

  private handleKeyUp(event: KeyboardEvent) {
    this.keyboardState.value.keys.delete(event.code);
  }

  private handleFocusIn(event: FocusEvent) {
    const target = event.target as HTMLElement;
    const elementIndex = this.elements.value.findIndex(
      (el) => el.element === target,
    );

    if (elementIndex !== -1) {
      this.currentFocusIndex.value = elementIndex;
      this.highlightElement(target);
    }
  }

  private handleFocusOut(event: FocusEvent) {
    const target = event.target as HTMLElement;
    this.removeHighlight(target);
  }

  private navigate(direction: "up" | "down" | "left" | "right") {
    if (this.elements.value.length === 0) return;

    const currentElement = this.elements.value[this.currentFocusIndex.value];
    if (!currentElement) return;

    let nextIndex = this.currentFocusIndex.value;

    switch (direction) {
      case "up":
        nextIndex = this.findNextElement(currentElement, "up");
        break;
      case "down":
        nextIndex = this.findNextElement(currentElement, "down");
        break;
      case "left":
        nextIndex = this.findNextElement(currentElement, "left");
        break;
      case "right":
        nextIndex = this.findNextElement(currentElement, "right");
        break;
    }

    if (nextIndex !== -1 && nextIndex !== this.currentFocusIndex.value) {
      this.currentFocusIndex.value = nextIndex;
      this.focusElement(nextIndex);
    }
  }

  private findNextElement(
    currentElement: NavigationElement,
    direction: string,
  ): number {
    const currentRect =
      currentElement.element.$el?.getBoundingClientRect() ||
      currentElement.element.getBoundingClientRect();
    const currentCenter = {
      x: currentRect.left + currentRect.width / 2,
      y: currentRect.top + currentRect.height / 2,
    };

    let bestCandidate = -1;
    let bestDistance = Infinity;

    for (let i = 0; i < this.elements.value.length; i++) {
      const candidate = this.elements.value[i];
      if (candidate.disabled || candidate.element === currentElement.element)
        continue;
      const candidateRect =
        candidate.element.$el?.getBoundingClientRect() ||
        candidate.element.getBoundingClientRect();
      const candidateCenter = {
        x: candidateRect.left + candidateRect.width / 2,
        y: candidateRect.top + candidateRect.height / 2,
      };

      let isValid = false;
      let distance = 0;

      switch (direction) {
        case "up":
          isValid = candidateCenter.y < currentCenter.y;
          distance =
            Math.abs(candidateCenter.x - currentCenter.x) +
            (currentCenter.y - candidateCenter.y);
          break;
        case "down":
          isValid = candidateCenter.y > currentCenter.y;
          distance =
            Math.abs(candidateCenter.x - currentCenter.x) +
            (candidateCenter.y - currentCenter.y);
          break;
        case "left":
          isValid = candidateCenter.x < currentCenter.x;
          distance =
            Math.abs(candidateCenter.y - currentCenter.y) +
            (currentCenter.x - candidateCenter.x);
          break;
        case "right":
          isValid = candidateCenter.x > currentCenter.x;
          distance =
            Math.abs(candidateCenter.y - currentCenter.y) +
            (candidateCenter.x - currentCenter.x);
          break;
      }

      if (isValid && distance < bestDistance) {
        bestDistance = distance;
        bestCandidate = i;
      }
    }

    return bestCandidate;
  }

  private focusElement(index: number) {
    const element = this.elements.value[index];
    if (element && !element.disabled) {
      element.element.focus();
      this.highlightElement(element.element);
    }
  }

  private highlightElement(element: HTMLElement) {
    element.style.outline = "2px solid #1976d2";
    element.style.outlineOffset = "2px";
    element.style.transform = "scale(1.02)";
    element.style.transition = "all 0.2s ease";
  }

  private removeHighlight(element: HTMLElement) {
    element.style.outline = "";
    element.style.outlineOffset = "";
    element.style.transform = "";
    element.style.transition = "";
  }

  private activate() {
    const currentElement = this.elements.value[this.currentFocusIndex.value];
    if (!currentElement || currentElement.disabled) return;

    if (currentElement.action) {
      currentElement.action();
    } else if (currentElement.route) {
      this.router.push({ name: currentElement.route as any });
    } else {
      currentElement.element.click();
    }
  }

  private goBack() {
    if (this.router.currentRoute.value.name !== ROUTES.HOME) {
      this.router.back();
    }
  }

  private goHome() {
    this.navigationStore.goHome();
  }

  private goSearch() {
    this.navigationStore.goSearch();
  }

  private goScan() {
    this.navigationStore.goScan();
  }

  private openPlatforms() {
    this.navigationStore.switchActivePlatformsDrawer();
  }

  private openCollections() {
    this.navigationStore.switchActiveCollectionsDrawer();
  }

  private openMenu() {
    this.navigationStore.switchActiveSettingsDrawer();
  }

  private togglePause() {
    // This could be used to pause/resume media playback or toggle fullscreen
    console.log("Toggle pause/menu");
  }

  // Public API
  public registerElement(element: NavigationElement) {
    this.elements.value.push(element);
    this.elements.value.sort((a, b) => a.priority - b.priority);
  }

  public unregisterElement(id: string) {
    const index = this.elements.value.findIndex((el) => el.id === id);
    if (index !== -1) {
      this.elements.value.splice(index, 1);
    }
  }

  public setEnabled(enabled: boolean) {
    this.isEnabled.value = enabled;
  }

  public getCurrentFocus() {
    return this.elements.value[this.currentFocusIndex.value];
  }

  public focusFirstElement() {
    if (this.elements.value.length > 0) {
      this.currentFocusIndex.value = 0;
      this.focusElement(0);
    }
  }

  public focusElementById(id: string) {
    const index = this.elements.value.findIndex((el) => el.id === id);
    if (index !== -1) {
      this.currentFocusIndex.value = index;
      this.focusElement(index);
    }
  }

  public getState() {
    return {
      isEnabled: this.isEnabled.value,
      currentFocusIndex: this.currentFocusIndex.value,
      gamepadConnected: this.gamepadState.value.connected,
      elementsCount: this.elements.value.length,
    };
  }

  public destroy() {
    document.removeEventListener("keydown", this.handleKeyDown.bind(this));
    document.removeEventListener("keyup", this.handleKeyUp.bind(this));
    window.removeEventListener(
      "gamepadconnected",
      this.handleGamepadConnected.bind(this),
    );
    window.removeEventListener(
      "gamepaddisconnected",
      this.handleGamepadDisconnected.bind(this),
    );
    document.removeEventListener("focusin", this.handleFocusIn.bind(this));
    document.removeEventListener("focusout", this.handleFocusOut.bind(this));
  }
}

// Create singleton instance
let navigationControllerInstance: NavigationController | null = null;

export function useNavigationController() {
  if (!navigationControllerInstance) {
    navigationControllerInstance = new NavigationController();
  }

  return navigationControllerInstance;
}

export function createNavigationController() {
  return new NavigationController();
}

export default NavigationController;
