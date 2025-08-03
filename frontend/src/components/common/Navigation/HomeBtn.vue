<script setup lang="ts">
import { ROUTES } from "@/plugins/router";
import storeNavigation from "@/stores/navigation";
import RIsotipo from "@/components/common/RIsotipo.vue";
import { useDisplay } from "vuetify";
import { storeToRefs } from "pinia";
import { ref } from "vue";
import { useNavigation } from "@/composables/useNavigation";

const { smAndDown } = useDisplay();
const navigationStore = storeNavigation();
const { mainBarCollapsed } = storeToRefs(navigationStore);

const homeBtnRef = ref<HTMLElement>();

useNavigation(homeBtnRef, "home-btn", {
  priority: 1,
  route: ROUTES.HOME,
  action: () => navigationStore.goHome(),
});
</script>

<template>
  <router-link
    ref="homeBtnRef"
    :to="{ name: ROUTES.HOME }"
    class="cursor-pointer"
    v-navigation="{ id: 'home-btn', priority: 1, route: 'home' }"
  >
    <r-isotipo :size="smAndDown ? 35 : 40" :avatar="mainBarCollapsed" />
  </router-link>
</template>
