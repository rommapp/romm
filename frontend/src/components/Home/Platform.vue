<script setup>
const props = defineProps(['platform', 'rail'])
</script>

<template>
    <router-link style="text-decoration: none; color: inherit;" :to="`/platform/${platform.slug}`">
        <v-hover v-slot="{ isHovering, props }">
            <v-card v-bind="props" :class="{ 'on-hover': isHovering }" :elevation="isHovering ? 20 : 3">
                <v-card-text>
                    <v-avatar :rounded="0" size="100%">
                        <v-img :src="'/assets/platforms/' + platform.slug + '.ico'"></v-img>
                    </v-avatar>
                    <v-chip class="bg-chip position-absolute" size="small" style="bottom: 1rem; right: 1rem" label>{{
                        platform.n_roms }}</v-chip>
                </v-card-text>
            </v-card>
        </v-hover>
    </router-link>
</template>

<style scoped>
</style>
