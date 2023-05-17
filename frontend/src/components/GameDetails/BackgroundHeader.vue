<script setup>
const props = defineProps(['rom'])
</script>

<template>
    <v-card class="header-background" position="absolute" rounded="0" flat>
        <v-img :src="'/assets/romm/resources/'+rom.path_cover_s" class="header-background-img" cover/>
    </v-card>
</template>

<style scoped>
.header-background { top: 0px; left: 0px; width: 100%; max-height: 330px; }
.header-background-img { -webkit-filter: blur(15px); filter: blur(15px); }
</style>