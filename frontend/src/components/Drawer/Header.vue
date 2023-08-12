<script setup>
import RailBtn from "@/components/Drawer/RailBtn.vue";

const props = defineProps(["rail"]);
</script>
<template>
  <v-list-item class="ml-2 mt-2 mb-2">
    <span class="text-h5 text-truncate ml-4">{{ rail ? "" : "RomM" }}</span>
    <template v-slot:prepend>
      <router-link to="/">
        <v-avatar :rounded="0" size="60" class=""
          ><v-img src="/assets/isotipo.svg"
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
