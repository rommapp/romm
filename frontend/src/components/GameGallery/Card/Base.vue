<script setup>
import ActionBar from '@/components/GameGallery/Card/ActionBar.vue'
import Cover from '@/components/GameGallery/Card/Cover.vue'
import { storeDownloading } from '@/stores/downloading.js'

// Props
const props = defineProps(['rom'])
const downloading = storeDownloading()
</script>

<template>
    <v-hover v-slot="{isHovering, props}">
        <v-card 
            :loading="downloading.value.includes(rom.file_name) ? 'rommAccent1': null"
            v-bind="props"
            :class="{'on-hover': isHovering}"
            :elevation="isHovering ? 20 : 3">
            <v-hover v-slot="{isHovering, props}" open-delay="800">
                <cover :rom="rom" :isHovering="isHovering" :hoverProps="props"/>
                <action-bar :rom="rom"/>
            </v-hover>
        </v-card>
    </v-hover>
</template>

<style scoped>
.v-card.on-hover { opacity: 1; }
.v-card:not(.on-hover) { opacity: 0.85; }
</style>