import cronstrue from "cronstrue";

export const views = {
  0: {
    view: "small",
    icon: "mdi-view-comfy",
    "size-xl": 1,
    "size-lg": 2,
    "size-md": 2,
    "size-sm": 2,
    "size-xs": 3,
    "size-cols": 4,
  },
  1: {
    view: "big",
    icon: "mdi-view-module",
    "size-xl": 2,
    "size-lg": 3,
    "size-md": 3,
    "size-sm": 3,
    "size-xs": 6,
    "size-cols": 6,
  },
  2: {
    view: "list",
    icon: "mdi-view-list",
    "size-xl": 12,
    "size-lg": 12,
    "size-md": 12,
    "size-sm": 12,
    "size-xs": 12,
    "size-cols": 12,
  },
};

export const defaultAvatarPath = "/assets/default_avatar.png";

export function toTop() {
  window.scrollTo({
    top: 0,
    left: 0,
    behavior: "smooth",
  });
}

export function normalizeString(s) {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

export function convertCronExperssion(expression) {
  let convertedExpression = cronstrue.toString(expression, { verbose: true });
  convertedExpression =
    convertedExpression.charAt(0).toLocaleLowerCase() +
    convertedExpression.substr(1);
  return convertedExpression;
}
