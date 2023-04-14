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

const rommDark = {
  dark: true,
  colors: {
    primary: '#161B22',
    secondary: '#424242',
    background: '#0D1117',
    rommAccent: '#A453FF',
    notification: '#0D1117',
    surface: '#161B22',
    tooltip: '#161B22',
    chip: '#161B22',
    info: '#2196F3',
    success: '#4CAF50',
    warning: '#FB8C00',
    error: '#B00020',
    red: '#DA3633'
  }
}

export default createVuetify({
  icons: {
    iconfont: 'mdi'
  },
  theme: {
    defaultTheme: 'rommDark',
    themes: {
      rommDark
    }
  }
})