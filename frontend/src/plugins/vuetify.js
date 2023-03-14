/**
 * plugins/vuetify.js
 *
 * Framework documentation: https://vuetifyjs.com`
 */

// Styles
import '@mdi/font/css/materialdesignicons.css'
import 'vuetify/styles'

// Composables
import { createVuetify } from 'vuetify'

// https://vuetifyjs.com/en/introduction/why-vuetify/#feature-guides
export default createVuetify({
  theme: {
    defaultTheme: 'dark',
    themes: {
      dark: {
        colors: {
          primary: '#212121',
          secondary: '#BDBDBD',
          toolbar: '#212121',
        },
      },
      light: {
        colors: {
          primary: '#1867C0',
          secondary: '#42A5F5',
          toolbar: '#42A5F5'
        }
      }
    }
  }
})
