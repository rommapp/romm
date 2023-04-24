<script setup>
import { views } from '@/utils/utils.js'
import { storeGalleryView } from '@/stores/galleryView.js'

// Props
const galleryView = storeGalleryView()
</script>

<template>
    <v-app-bar-nav-icon
        @click="galleryView.next()"
        rounded="0"
        variant="plain">
        <v-icon :icon="views[galleryView.value]['icon']"/>
    </v-app-bar-nav-icon>
</template>