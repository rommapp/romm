import type { Directive, DirectiveBinding } from "vue";
import { useNavigationController } from "@/utils/navigation-controller";

interface NavigationBindingValue {
  id: string;
  priority?: number;
  route?: string;
  action?: () => void;
  disabled?: boolean;
}

export const vNavigation: Directive = {
  mounted(el: HTMLElement, binding: DirectiveBinding) {
    const navigationController = useNavigationController();

    const value = binding.value as NavigationBindingValue;

    if (!value || !value.id) {
      console.warn(
        "v-navigation directive requires an id in the binding value",
      );
      return;
    }

    // Make element focusable if it isn't already
    if (!el.hasAttribute("tabindex")) {
      el.setAttribute("tabindex", "0");
    }

    // Add navigation element to controller
    const element = {
      id: value.id,
      element: el,
      priority: value.priority || 100,
      route: value.route,
      action: value.action,
      disabled: value.disabled || false,
    };

    navigationController.registerElement(element);

    // Store reference for cleanup
    el._navigationId = value.id;

    // Add visual feedback for focus
    el.addEventListener("focus", () => {
      el.classList.add("navigation-focused");
    });

    el.addEventListener("blur", () => {
      el.classList.remove("navigation-focused");
    });

    // Add click handler for activation
    el.addEventListener("click", () => {
      if (value.action) {
        value.action();
      } else if (value.route) {
        // This would need to be handled by the component or router
        console.log("Route navigation:", value.route);
      }
    });
  },

  updated(el: HTMLElement, binding: DirectiveBinding) {
    const navigationController = useNavigationController();

    const value = binding.value as NavigationBindingValue;

    if (!value || !value.id) return;

    // Update the element in the controller
    navigationController.unregisterElement(value.id);

    const element = {
      id: value.id,
      element: el,
      priority: value.priority || 100,
      route: value.route,
      action: value.action,
      disabled: value.disabled || false,
    };

    navigationController.registerElement(element);
  },

  unmounted(el: HTMLElement) {
    const navigationController = useNavigationController();

    if (el._navigationId) {
      navigationController.unregisterElement(el._navigationId);
      delete el._navigationId;
    }
  },
};

// Directive for navigation groups
export const vNavigationGroup: Directive = {
  mounted(el: HTMLElement, binding: DirectiveBinding) {
    const groupId = binding.value as string;

    if (!groupId) {
      console.warn("v-navigation-group directive requires a group id");
      return;
    }

    el._navigationGroupId = groupId;
    el.classList.add("navigation-group");
  },

  unmounted(el: HTMLElement) {
    delete el._navigationGroupId;
    el.classList.remove("navigation-group");
  },
};

// Directive for navigation containers
export const vNavigationContainer: Directive = {
  mounted(el: HTMLElement, binding: DirectiveBinding) {
    const containerId = binding.value as string;

    if (!containerId) {
      console.warn("v-navigation-container directive requires a container id");
      return;
    }

    el._navigationContainerId = containerId;
    el.classList.add("navigation-container");

    // Focus first element when container is focused
    el.addEventListener("focusin", (event) => {
      const target = event.target as HTMLElement;
      if (target.closest(".navigation-container") === el) {
        // Find first focusable element in this container
        const firstFocusable = el.querySelector(
          '[tabindex]:not([tabindex="-1"])',
        ) as HTMLElement;
        if (firstFocusable && firstFocusable !== target) {
          firstFocusable.focus();
        }
      }
    });
  },

  unmounted(el: HTMLElement) {
    delete el._navigationContainerId;
    el.classList.remove("navigation-container");
  },
};

// Register all directives
export function registerNavigationDirectives(app: any) {
  app.directive("navigation", vNavigation);
  app.directive("navigation-group", vNavigationGroup);
  app.directive("navigation-container", vNavigationContainer);
}
