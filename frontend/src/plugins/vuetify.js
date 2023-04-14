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
    primary:      '#161b22',
    secondary:    '#a452fe',
    background:   '#0d1117',

    notification: '#0d1117',
    surface:      '#161b22',
    tooltip:      '#161b22',
    chip:         '#161b22',
    
    rommAccent1:  '#a452fe',
    rommAccent2:  '#c400f7',
    rommAccent2:  '#3808a4',
    rommWhite:    '#fefdfe',
    rommBlack:    '#000000',
    rommRed:      '#da3633',
    rommGreen:    '#3FB950'
  }
}
const rommLight = {
  dark: false,
  colors: {
    primary:      '#fefdfe',
    secondary:    '#a452fe',
    background:   '#fefdfe',

    notification: '#0d1117',
    surface:      '#fefdfe',
    tooltip:      '#fefdfe',
    chip:         '#161b22',
    
    rommAccent1:  '#a452fe',
    rommAccent2:  '#c400f7',
    rommAccent2:  '#3808a4',
    rommWhite:    '#fefdfe',
    rommBlack:    '#000000',
    rommRed:      '#da3633',
    rommGreen:    '#3FB950'
  }
}

export default createVuetify({
  icons: {
    iconfont: 'mdi'
  },
  theme: {
    defaultTheme: 'rommDark',
    themes: {
      rommDark,
      rommLight
    }
  }
})