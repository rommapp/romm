// Composables
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('@/views/Home.vue')
  },
  {
    path: '/:platform',
    component: () => import('@/views/Gallery.vue')
  },
  {
    path: '/:platform/roms/:rom',
    component: () => import('@/views/Details.vue')
  }
]

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes,
})

export default router
