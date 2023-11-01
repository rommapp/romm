const commonColors = {
  "romm-accent-1": "#a452fe",
  "romm-accent-2": "#c400f7",
  "romm-accent-3": "#3808a4",

  "romm-red": "#da3633",
  "romm-green": "#3FB950",
  "romm-white": "#fefdfe",
  "romm-gray": "#5D5D5D",
  "romm-black": "#000000",
};

export const dark = {
  dark: true,
  colors: {
    primary: "#161b22",
    secondary: "#0d1117",
    terciary: "#202832",
    background: "#0d1117",

    surface: "#161b22",
    tooltip: "#202832",
    chip: "#161b22",

    ...commonColors,
  },
};

export const light = {
  dark: false,
  colors: {
    primary: "#ECEFF4",
    secondary: "#ECEFF4",
    terciary: "#ECEFF4",
    background: "#ECEFF4",

    surface: "#ECEFF4",
    tooltip: "#ECEFF4",
    chip: "#ECEFF4",

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
