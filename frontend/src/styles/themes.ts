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
    primary: "#8B74E8", // Slightly desaturated for better readability
    secondary: "#9E8CD6", // Better contrast with primary
    tertiary: "#C5B6AE", // Lightened for better visibility
    accent: "#FF9B85", // Slightly muted to reduce visual harshness
    background: "#0D1117",
    surface: "#161B22",
    toplayer: "#1C2330", // Slightly darker for better depth
    "primary-lighten": "#A18FFF", // More vibrant for interactive elements
    "primary-darken": "#6043C8", // Deeper purple for emphasis
    "secondary-lighten": "#EBE7FA", // More saturated for better contrast
    "secondary-darken": "#7A6BB4", // Darker for better hierarchy
    "tertiary-lighten": "#E5D6CC", // Warmer tone
    "tertiary-darken": "#A69589", // More neutral dark tone
    ...commonColors,
  },
};

export const light = {
  dark: false,
  colors: {
    primary: "#5D3AB8", // Slightly darker for better contrast on light
    secondary: "#7B5EC9",
    tertiary: "#8A7A71", // Darker for better readability
    accent: "#FF7A5C", // More vibrant for better visibility
    surface: "#FFFFFF",
    background: "#F2F4F8", // Darker to create more separation from background
    toplayer: "#E4E9F0",
    "primary-lighten": "#7850E6", // More saturated for interactive states
    "primary-darken": "#452788",
    "secondary-lighten": "#F0EBFA", // Slightly warmer purple tint
    "secondary-darken": "#9B8BD0", // More saturated for emphasis
    "tertiary-lighten": "#CFC2B8",
    "tertiary-darken": "#766961", // Darker for better contrast
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
