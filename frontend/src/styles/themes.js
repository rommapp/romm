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

export const rommDark = {
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

export const rommLight = {
  dark: false,
  colors: {
    primary: "#fefdfe",
    secondary: "#fefdfe",
    terciary: "#fefdfe",
    background: "#fefdfe",

    surface: "#fefdfe",
    tooltip: "#fefdfe",
    chip: "#fefdfe",

    ...commonColors,
  },
};

export const themes = {
  0: "rommDark",
  1: "rommLight",
};
