<script setup>
import { ref, inject } from 'vue'
import { downloadRom, downloadSave } from '@/services/download.js'

// Props
const props = defineProps(['rom'])
const saveFiles = ref(false)

// Event listeners bus
const emitter = inject('emitter')
</script>

<template>
    <v-card-text>
        <v-row>
            <v-col class="pa-0">
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
                :disabled="!saveFiles"/>
        </v-row>
    </v-card-text>
</template>