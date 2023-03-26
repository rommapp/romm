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
  defaults: {
    vSelect: { variant: 'outlined' },
    vTextField: { variant: 'outlined' },
    vFileInput: { variant: 'outlined' }
  },
  theme: {
    defaultTheme: 'dark',
    themes: {
      light: {
        colors: {
          primary: '#FFFFFF',
          secondary: '#BDBDBD',
          toolbar: '#FFFFFF',
          background: '#FFFFFF'
        }
      },
      dark: {
        colors: {
          primary: '#212121',
          secondary: '#424242',
          toolbar: '#212121',
          background: '#212121'
        }
      }
    }
  }
})