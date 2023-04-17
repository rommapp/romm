<script setup>
import { ref, inject } from 'vue'
import { downloadRom, downloadSave } from '@/utils/utils.js'

// Props
const props = defineProps(['rom'])
const forceImgReload = Date.now()
const saveFiles = ref(false)

// Event listeners bus
const emitter = inject('emitter')
</script>

<template>
    <v-list-item 
        :to="`/${$route.params.platform}/roms/${rom.file_name}`"
        :value="rom.file_name"
        :key="rom.file_name"
        class="pa-2">
        <v-row class="text-subtitle-2">
            <v-col md="3" lg="3"><p>{{ rom.r_name }}</p></v-col>
            <v-col md="3" lg="4" class="hidden-sm-and-down"><p>{{ rom.file_name }}</p></v-col>
            <v-col class="hidden-sm-and-down"><p>{{ rom.p_slug }}</p></v-col>
            <v-col class="hidden-sm-and-down"><p>{{ rom.file_size }} {{ rom.file_size_units }}</p></v-col>
            <v-col class="hidden-sm-and-down"><p>{{ rom.region }}</p></v-col>
            <v-col class="hidden-sm-and-down"><p>{{ rom.revision }}</p></v-col>
        </v-row>
        <template v-slot:prepend>
            <v-avatar :rounded="0" class="ml-3">
                <v-img
                    :src="'/assets'+rom.path_cover_l+'?reload='+forceImgReload"
                    :lazy-src="'/assets'+rom.path_cover_s+'?reload='+forceImgReload"
                    min-height="100"/>
            </v-avatar>
        </template>
        <template v-slot:append>
            <v-col class="pa-0 ml-1">
            <v-btn
                @click="downloadRom(rom, emitter)"
                icon="mdi-download"
                size="x-small"
                variant="text"/>
            <v-btn
                @click="downloadSave(rom, emitter)"
                icon="mdi-content-save-all"
                size="x-small"
                variant="text"
                :disabled="!saveFiles"/>
            </v-col>
            <v-btn
                @click=""
                icon="mdi-dots-vertical"
                size="x-small"
                variant="text"
                class="mr-3"
                :disabled="!saveFiles"/>
        </template>
    </v-list-item>
</template>