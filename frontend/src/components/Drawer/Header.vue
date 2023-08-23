<script setup>
import RailBtn from "@/components/Drawer/RailBtn.vue";

const props = defineProps(["rail"]);
</script>
<template>
  <v-list-item :class="{ 'ml-9': !rail, 'ml-0': rail }" class="my-2">
    <template v-slot:prepend>
      <router-link to="/">
        <v-avatar :rounded="0" :size="rail ? 40 : 60" class="mr-3"
          ><v-img src="/assets/isotipo.svg"
        /></v-avatar>
        <v-avatar v-if="!rail" :rounded="0" size="60"
          ><v-img src="/assets/logotipo.svg"
        /></v-avatar>
      </router-link>
    </template>
    <template v-if="!rail" v-slot:append>
      <rail-btn :rail="rail" />
    </template>
  </v-list-item>
  <v-list-item class="pa-0" v-if="rail">
    <rail-btn :rail="rail" />
  </v-list-item>
</template>

<style scoped>
.home-btn {
  width: 75px;
  cursor: pointer;
}
</style>
