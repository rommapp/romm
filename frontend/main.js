import { createApp } from 'vue'
import App from './App.vue'
import Game from './components/Game.vue'

import './assets/main.css'

const app = createApp(App)
app.component('Game', Game);
app.mount('#app');