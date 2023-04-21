// Composables
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('@/views/Home.vue')
  },
  {
    path: '/platform/:platform',
    component: () => import('@/views/Gallery.vue')
  },
  {
    path: '/platform/:platform/rom/:rom',
    component: () => import('@/views/Details.vue')
  }
]

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes,
})

export default router
