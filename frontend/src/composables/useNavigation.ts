import { ref, onMounted, onUnmounted, nextTick, type Ref } from "vue";
import {
  useNavigationController,
  type NavigationElement,
} from "@/utils/navigation-controller";

export interface UseNavigationOptions {
  autoRegister?: boolean;
  priority?: number;
  route?: string;
  action?: () => void;
  disabled?: Ref<boolean>;
}

export function useNavigation(
  elementRef: Ref<HTMLElement | undefined>,
  id: string,
  options: UseNavigationOptions = {},
) {
  const navigationController = useNavigationController();
  const isRegistered = ref(false);

  const {
    autoRegister = true,
    priority = 100,
    route,
    action,
    disabled = ref(false),
  } = options;

  const registerElement = async () => {
    if (!elementRef.value || isRegistered.value) return;

    await nextTick();

    const element: NavigationElement = {
      id,
      element: elementRef.value,
      priority,
      route,
      action,
      disabled: disabled.value,
    };

    navigationController.registerElement(element);
    isRegistered.value = true;
  };

  const unregisterElement = () => {
    if (!isRegistered.value) return;

    navigationController.unregisterElement(id);
    isRegistered.value = false;
  };

  const focus = () => {
    navigationController.focusElementById(id);
  };

  const isFocused = () => {
    const currentFocus = navigationController.getCurrentFocus();
    return currentFocus?.id === id;
  };

  const getState = () => {
    return navigationController.getState();
  };

  // Auto-register on mount if enabled
  onMounted(() => {
    if (autoRegister) {
      registerElement();
    }
  });

  // Auto-unregister on unmount
  onUnmounted(() => {
    unregisterElement();
  });

  return {
    registerElement,
    unregisterElement,
    focus,
    isFocused,
    getState,
    isRegistered,
  };
}

// Composable for managing navigation groups
export function useNavigationGroup(groupId: string) {
  const navigationController = useNavigationController();
  const elements = ref<NavigationElement[]>([]);

  const addElement = (element: NavigationElement) => {
    element.id = `${groupId}-${element.id}`;
    elements.value.push(element);
    navigationController.registerElement(element);
  };

  const removeElement = (id: string) => {
    const fullId = `${groupId}-${id}`;
    const index = elements.value.findIndex((el) => el.id === fullId);
    if (index !== -1) {
      elements.value.splice(index, 1);
      navigationController.unregisterElement(fullId);
    }
  };

  const focusFirst = () => {
    if (elements.value.length > 0) {
      navigationController.focusElementById(elements.value[0].id);
    }
  };

  const focusLast = () => {
    if (elements.value.length > 0) {
      const lastElement = elements.value[elements.value.length - 1];
      navigationController.focusElementById(lastElement.id);
    }
  };

  const clear = () => {
    elements.value.forEach((element) => {
      navigationController.unregisterElement(element.id);
    });
    elements.value = [];
  };

  onUnmounted(() => {
    clear();
  });

  return {
    addElement,
    removeElement,
    focusFirst,
    focusLast,
    clear,
    elements,
  };
}

// Composable for keyboard shortcuts
export function useKeyboardShortcuts() {
  const navigationController = useNavigationController();

  const addShortcut = (key: string, action: () => void) => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.code === key) {
        event.preventDefault();
        action();
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  };

  const addShortcutWithModifier = (
    key: string,
    modifier: "ctrl" | "alt" | "shift",
    action: () => void,
  ) => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const modifierPressed =
        modifier === "ctrl"
          ? event.ctrlKey
          : modifier === "alt"
            ? event.altKey
            : modifier === "shift"
              ? event.shiftKey
              : false;

      if (event.code === key && modifierPressed) {
        event.preventDefault();
        action();
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  };

  return {
    addShortcut,
    addShortcutWithModifier,
  };
}

// Composable for gamepad support
export function useGamepadSupport() {
  const navigationController = useNavigationController();
  const isGamepadConnected = ref(false);

  const checkGamepadConnection = () => {
    const gamepads = navigator.getGamepads();
    isGamepadConnected.value = gamepads.some((gamepad) => gamepad !== null);
  };

  onMounted(() => {
    checkGamepadConnection();

    window.addEventListener("gamepadconnected", checkGamepadConnection);
    window.addEventListener("gamepaddisconnected", checkGamepadConnection);
  });

  onUnmounted(() => {
    window.removeEventListener("gamepadconnected", checkGamepadConnection);
    window.removeEventListener("gamepaddisconnected", checkGamepadConnection);
  });

  return {
    isGamepadConnected,
  };
}
