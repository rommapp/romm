<script setup>
// Props
const props = defineProps(['platform', 'rail'])
</script>

<template>
    <v-list-item :to="`/platform/${platform.slug}`" :value="platform.slug" :key="platform" class="pt-4 pb-4 bg-terciary">
        <span class="text-body-2 text-truncate">{{ rail ? '' : platform.name }}</span>
        <template v-slot:prepend>
            <v-avatar :rounded="0" size="40"><v-img :src="'/assets/platforms/'+platform.slug+'.ico'"></v-img></v-avatar>
        </template>
        <template v-slot:append>
            <v-chip class="ml-4 bg-chip" size="x-small" label>{{ platform.n_roms }}</v-chip>
        </template>
    </v-list-item>
</template>

<style scoped>
</style>