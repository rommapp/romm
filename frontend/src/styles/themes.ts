const commonColors = {
  "romm-red": "#da3633",
  "romm-green": "#3FB950",
  "romm-white": "#fefdfe",
  "romm-gray": "#5D5D5D",
  "romm-black": "#000000",
};

export const dark = {
  dark: true,
  colors: {
    primary: "#8168E6",
    secondary: "#9584D1",
    tertiary: "#D4C4B9",
    accent: "#FFB6A3",
    background: "#0D1117",
    surface: "#161B22",
    toplayer: "#202832",
    "primary-lighten": "#6B42CC",
    "primary-darken": "#4527A0",
    "secondary-lighten": "#F5F2FC",
    "secondary-darken": "#D1C9F2",
    "tertiary-lighten": "#FFD0C4",
    "tertiary-darken": "#FFA089",
    ...commonColors,
  },
};

export const light = {
  dark: false,
  colors: {
    primary: "#5933B3",
    secondary: "#E6E1F9",
    tertiary: "#FFB6A3",
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
