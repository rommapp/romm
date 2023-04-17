<script setup>
// Props
const props = defineProps(['platform', 'rail'])


</script>

<template>
    <v-list-item :to="`/${platform.slug}`" :value="platform.slug" :key="platform" class="pt-4 pb-4">
        <p class="text-subtitle-2 text-truncate">{{ rail ? '' : platform.name }}</p>
        <template v-slot:prepend>
            <v-avatar :rounded="0"><v-img :src="'/assets/platforms/'+platform.slug+'.ico'"></v-img></v-avatar>
        </template>
        <template v-slot:append>
            <v-chip class="ml-4 bg-chip" size="small">{{ platform.n_roms }}</v-chip>
        </template>
    </v-list-item>
</template>

<style scoped>
.v-navigation-drawer--rail:not(.v-navigation-drawer--is-hovering) .v-list .v-avatar {
  --v-avatar-height: 40px;
}
</style>