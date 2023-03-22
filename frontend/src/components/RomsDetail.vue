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
    <v-row class="text-body-1 justify-center">
        <v-col cols="8" xs="8" sm="4" md="3" lg="2">
            <v-card >
                <v-img :src="rom.path_cover_l" :lazy-src="rom.path_cover_s" cover >
                    <template v-slot:placeholder>
                        <div class="d-flex align-center justify-center fill-height">
                            <v-progress-circular color="grey-lighten-4" indeterminate />
                        </div>
                    </template>
                    <div v-if="!rom.r_slug" class="d-flex align-center pt-2 pr-5 pb-2 pl-5 bg-secondary rom-title" >{{ rom.name }}</div>
                </v-img>
            </v-card>
            <div>
                <v-btn class="mt-2" prepend-icon="mdi-download" @click="downloadRom()">Rom</v-btn>
                <v-btn class="mt-2 ml-2" prepend-icon="mdi-content-save-all" @click="downloadSaves()">Saves</v-btn>
            </div>
            <div>
                <v-btn class="mt-2" prepend-icon="mdi-pencil-box" @click="editRom(rom)">Edit</v-btn>
                <v-btn class="mt-2  ml-2" prepend-icon="mdi-magnify-scan" @click="scanRom(rom)">Scan</v-btn>
            </div>
        </v-col>
        <v-col class="mt-2 ml-3">
            <v-row>IGDB id: {{ rom.r_igdb_id }}</v-row>
            <v-row>Name: {{ rom.name }}</v-row>
            <v-row>File: {{ rom.filename }}</v-row>
            <v-row>Slug: {{ rom.r_slug }}</v-row>
            <v-row>Platform: {{ rom.p_slug }}</v-row>
            <v-row>Cover: {{ rom.path_cover_l }}</v-row>
            <v-divider class="mt-8 mb-8"></v-divider>
            <v-row class="pr-10">{{ rom.summary }}</v-row>
        </v-col>
    </v-row>
    <v-divider class="mt-10 mb-10 border-opacity-75"></v-divider>
</template>