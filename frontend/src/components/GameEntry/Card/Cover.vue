<script setup>
import { inject } from 'vue'
import { useRouter } from 'vue-router'
import { selectRom } from '@/utils/utils.js'

// Props
const props = defineProps(['rom', 'isHovering', 'hoverProps', 'size'])
const forceImgReload = Date.now()
const router = useRouter()

// Event listeners bus
const emitter = inject('emitter')
</script>

<template>
    <v-img 
        @click="selectRom(rom, emitter, router)"
        v-bind="hoverProps"
        :src="'/assets'+rom.path_cover_l+'?reload='+forceImgReload"
        :lazy-src="'/assets'+rom.path_cover_s+'?reload='+forceImgReload"
        class="cover"
        cover>
        <template v-slot:placeholder>
            <div class="d-flex align-center justify-center fill-height">
                <v-progress-circular indeterminate/>
            </div>
        </template>
        <v-expand-transition>
            <div 
                v-if="isHovering || !rom.has_cover"
                class="rom-title d-flex transition-fast-in-fast-out bg-secondary text-caption">
                <v-list-item>{{ rom.file_name }}</v-list-item>
            </div>
        </v-expand-transition>
        <div>
            <v-chip
                v-show="rom.region"
                class="ma-1 bg-primary"
                size="x-small">
                {{ rom.region }}
            </v-chip>
            <v-chip
                v-show="rom.revision"
                class="ma-1 bg-primary"
                size="x-small">
                {{ rom.revision }}
            </v-chip>
        </div>
    </v-img>
</template>

<style scoped>
.v-card .rom-title{
    transition: opacity .4s ease-in-out;
}
.rom-title.on-hover {
    opacity: 1;
}
.rom-title:not(.on-hover) {
    opacity: 0.85;
}
</style>