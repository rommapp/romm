import type { Plugin, App } from "vue";

function setViewTransitionName(
  el: HTMLElement,
  value: string | Record<string, boolean>,
  directiveName: "view-transition-name" | "trans",
) {
  if (typeof value === "string") {
    el.style.viewTransitionName = value;
  } else if (value && typeof value === "object") {
    const [viewTransitionName, active] = Object.entries(value)?.[0] || [];
    if (active) {
      el.style.viewTransitionName = viewTransitionName;
    } else {
      el.style.viewTransitionName = "none";
    }
  } else {
    throw new Error(
      `The value of \`v-${directiveName}\` should be either "string" or "object" but got "${typeof value}"`,
    );
  }
}

export default function vueTransitionPlugin(): Plugin {
  return {
    install(app: App) {
      if (!document.startViewTransition) return;

      app.directive("view-transition-name", {
        beforeMount(el: HTMLElement, binding) {
          setViewTransitionName(el, binding.value, "view-transition-name");
        },
        beforeUpdate(el: HTMLElement, binding) {
          setViewTransitionName(el, binding.value, "view-transition-name");
        },
      });

      app.directive("trans", {
        beforeMount(el: HTMLElement, binding) {
          setViewTransitionName(el, binding.value, "trans");
        },
        beforeUpdate(el: HTMLElement, binding) {
          setViewTransitionName(el, binding.value, "trans");
        },
      });
    },
  };
}
