/**
 * plugins/vuetify.js
 *
 * Framework documentation: https://vuetifyjs.com`
 */

// Styles
import "@mdi/font/css/materialdesignicons.css";
import "vuetify/styles";
import { rommDark, rommLight } from "@/styles/themes";

// Composables
import { createVuetify } from "vuetify";

export default createVuetify({
  icons: {
    iconfont: "mdi",
  },
  theme: {
    defaultTheme: "rommDark",
    themes: {
      rommDark,
      rommLight,
    },
  },
});
