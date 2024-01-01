import cronstrue from "cronstrue";

export const views = {
  0: {
    view: "small",
    icon: "mdi-view-comfy",
    "size-xl": 1,
    "size-lg": 1,
    "size-md": 2,
    "size-sm": 2,
    "size-xs": 3,
    "size-cols": 4,
  },
  1: {
    view: "big",
    icon: "mdi-view-module",
    "size-xl": 2,
    "size-lg": 2,
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

export function regionToEmoji(region) {
  switch (region.toLowerCase()) {
    case ("as", "australia"):
      return "🇦🇺";
    case ("a", "asia"):
      return "🌏";
    case ("b", "bra", "brazil"):
      return "🇧🇷";
    case ("c", "canada"):
      return "🇨🇦";
    case ("ch", "chn", "china"):
      return "🇨🇳";
    case ("e", "eu", "europe"):
      return "🇪🇺";
    case ("f", "france"):
      return "🇫🇷";
    case ("fn", "finland"):
      return "🇫🇮";
    case ("g", "germany"):
      return "🇩🇪";
    case ("gr", "greece"):
      return "🇬🇷";
    case ("h", "holland"):
      return "🇳🇱";
    case ("hk", "hong kong"):
      return "🇭🇰";
    case ("i", "italy"):
      return "🇮🇹";
    case ("j", "jp", "japan"):
      return "🇯🇵";
    case ("k", "korea"):
      return "🇰🇷";
    case ("nl", "netherlands"):
      return "🇳🇱";
    case ("no", "norway"):
      return "🇳🇴";
    case ("pd", "public domain"):
      return "🇵🇱";
    case ("r", "russia"):
      return "🇷🇺";
    case ("s", "spain"):
      return "🇪🇸";
    case ("sw", "sweden"):
      return "🇸🇪";
    case ("t", "taiwan"):
      return "🇹🇼";
    case ("u", "us", "usa"):
      return "🇺🇸";
    case ("uk", "england"):
      return "🇬🇧";
    case ("unk", "unknown"):
      return "🌎";
    case ("unl", "unlicensed"):
      return "🌎";
    case ("w", "global", "world"):
      return "🌎";
    default:
      return region;
  }
}

export function languageToEmoji(language) {
  switch (language.toLowerCase()) {
    case ("ar", "arabic"):
      return "🇦🇪";
    case ("da", "danish"):
      return "🇩🇰";
    case ("de", "german"):
      return "🇩🇪";
    case ("en", "english"):
      return "🇬🇧";
    case ("es", "spanish"):
      return "🇪🇸";
    case ("fi", "finnish"):
      return "🇫🇮";
    case ("fr", "french"):
      return "🇫🇷";
    case ("it", "italian"):
      return "🇮🇹";
    case ("ja", "japanese"):
      return "🇯🇵";
    case ("ko", "korean"):
      return "🇰🇷";
    case ("nl", "dutch"):
      return "🇳🇱";
    case ("no", "norwegian"):
      return "🇳🇴";
    case ("pl", "polish"):
      return "🇵🇱";
    case ("pt", "portuguese"):
      return "🇵🇹";
    case ("ru", "russian"):
      return "🇷🇺";
    case ("sv", "swedish"):
      return "🇸🇪";
    case ("zh", "chinese"):
      return "🇨🇳";
    case ("nolang", "no language"):
      return "🌎";
    default:
      return language;
  }
}
