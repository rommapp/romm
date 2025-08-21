const commonColors = {
  "romm-red": "#DA3633",
  "romm-green": "#3FB950",
  "romm-blue": "#0070F3",
  "romm-white": "#FEFDFE",
  "romm-gray": "#5D5D5D",
  "romm-black": "#000000",
  "romm-gold": "#FFD700",
};

export const dark = {
  dark: true,
  colors: {
    primary: "#8B74E8",
    secondary: "#9E8CD6",
    accent: "#E1A38D",
    background: "#0D1117",
    surface: "#161B22",
    toplayer: "#1C2330",
    "primary-lighten": "#A18FFF",
    "primary-darken": "#6043C8",
    "secondary-lighten": "#EBE7FA",
    "secondary-darken": "#7A6BB4",
    ...commonColors,
  },
};

export const light = {
  dark: false,
  colors: {
    primary: "#371f69",
    secondary: "#553E98",
    accent: "#E1A38D",
    surface: "#FFFFFF",
    background: "#F2F4F8",
    toplayer: "#E4E9F0",
    "primary-lighten": "#7850E6",
    "primary-darken": "#452788",
    "secondary-lighten": "#F0EBFA",
    "secondary-darken": "#9B8BD0",
    ...commonColors,
  },
};

export const darkThemeKey = 0;
export const lightThemeKey = 1;
export const autoThemeKey = 2;

export const themes = {
  [darkThemeKey]: "dark",
  [lightThemeKey]: "light",
  [autoThemeKey]: "auto",
};
