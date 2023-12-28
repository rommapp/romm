<script setup>
const props = defineProps(["image"]);
</script>

<template>
  <v-card id="header-background" position="absolute" rounded="0" flat>
    <v-img
      :src="`/assets/romm/resources/${image}`"
      id="header-background-img"
      cover
    />
  </v-card>
</template>

<style scoped>
#header-background {
  top: 0px;
  left: 0px;
  width: 100%;
  max-height: 330px;
}
#header-background-img {
  -webkit-filter: blur(15px);
  filter: blur(15px);
}
</style>
