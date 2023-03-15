/**
 * main.js
 *
 * Bootstraps Vuetify and other plugins then mounts the App`
 */

// Components
import App from './App.vue'

// Composables
import { createApp } from 'vue'

// Plugins
import { registerPlugins } from '@/plugins'

// Event bus
import mitt from 'mitt'
const emitter = mitt()

const app = createApp(App)

registerPlugins(app)

app.provide('emitter', emitter);
app.mount('#app')
