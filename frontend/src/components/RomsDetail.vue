<script setup>
import axios from 'axios'
import { ref, inject } from "vue";

// Props
const rom = ref("")
rom.value = JSON.parse(localStorage.getItem('currentRom')) || ''

// Event listeners bus
const emitter = inject('emitter')
emitter.on('currentRom', (currentRom) => { rom.value = currentRom })

// Functions


</script>

<template>
    <v-row>
        <v-col cols="2">
            <v-card >
                <v-img :src="rom.path_cover_big" :lazy-src="rom.path_cover_smallt" cover >
                    <template v-slot:placeholder>
                        <div class="d-flex align-center justify-center fill-height">
                            <v-progress-circular color="grey-lighten-4" indeterminate />
                        </div>
                    </template>
                    <div v-if="!rom.slug" class="d-flex align-center text-body-1 pt-2 pr-5 pb-2 pl-5 bg-secondary rom-title" >{{ rom.name }}</div>
                </v-img>
            </v-card>
        </v-col>
        <v-col class="mt-2">
            <v-row><div class="text-h6 justify-center">IGDB id: {{ rom.igdb_id }}</div></v-row>
            <v-row><div class="text-h6 justify-center">Name: {{ rom.name }}</div></v-row>
            <v-row><div class="text-h6 justify-center">File: {{ rom.filename }}</div></v-row>
            <v-row><div class="text-h6 justify-center">Slug: {{ rom.slug }}</div></v-row>
            <v-row><div class="text-h6 justify-center">Platform: {{ rom.platform_slug }}</div></v-row>
            <v-row><div class="text-h6 justify-center">Cover: {{ rom.path_cover_big }}</div></v-row>
            <v-divider class="mt-8"></v-divider>
            <v-row class="mt-3" max-width="200">
                <v-col cols="2"><v-btn block prepend-icon="mdi mdi-download">Download</v-btn></v-col>
                <v-col cols="3"><v-btn block prepend-icon="mdi mdi-content-save-all">Download save files</v-btn></v-col>
            </v-row>
            <v-row>
                <v-col cols="2">
                    <v-btn block prepend-icon="mdi mdi-square-edit-outline">Edit</v-btn>
                </v-col>
            </v-row>
        </v-col>
    </v-row>
    <v-row>
        <v-col>
            <p class="text-h6 justify-center">{{ rom.summary }}</p>
        </v-col>
    </v-row>
</template>