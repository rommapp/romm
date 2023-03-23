<script setup>
import axios from 'axios'
import { ref, inject } from "vue";

// Props
const rom = ref("")
const scanOverwrite = ref(false)
rom.value = JSON.parse(localStorage.getItem('currentRom')) || ''

// Event listeners bus
const emitter = inject('emitter')
emitter.on('currentRom', (currentRom) => { rom.value = currentRom })

// Functions
async function scanRom() {
    console.log("scanning rom... "+rom.value.filename)
    await axios.put('/api/scan/rom?overwrite='+scanOverwrite.value, {
        filename: rom.value.filename,
        p_slug: rom.value.p_slug,
        p_igdb_id: rom.value.p_igdb_id
    }).then((response) => {
        console.log("scan "+rom.value.filename+" completed")
        console.log(response.data)
    }).catch((error) => {console.log(error)})
}

</script>

<template>
    <v-row class="text-body-1 justify-center">
        <v-col cols="8" xs="8" sm="4" md="3" lg="2">
            <v-container fluid class="pa-0">
                <v-row>
                    <v-col>
                        <v-card >
                            <v-img :src="rom.path_cover_l" :lazy-src="rom.path_cover_s" cover >
                                <template v-slot:placeholder>
                                    <div class="d-flex align-center justify-center fill-height">
                                        <v-progress-circular color="grey-lighten-4" indeterminate />
                                    </div>
                                </template>
                            </v-img>
                        </v-card>
                    </v-col>
                </v-row>
                <v-row class="pt-1 pb-1 pl-2 pr-2 mt-0">
                    <v-container>
                        <v-row>
                            <v-col class="pa-1">
                                <v-btn rounded="0" @click="downloadRom()" block><v-icon size="large" icon="mdi-download"/></v-btn>
                            </v-col>
                            <v-col class="pa-1">
                                <v-btn rounded="0" @click="downloadSaves()" block><v-icon size="large" icon="mdi-content-save-all"/></v-btn>
                            </v-col>
                            <v-col class="pa-1">
                                <v-menu location="bottom">
                                    <template v-slot:activator="{ props }">
                                        <v-btn rounded="0" block v-bind="props"><v-icon size="large" icon="mdi-dots-vertical"/></v-btn>
                                    </template>
                                    <v-list rounded="0">
                                        <v-list-item key="search_igdb" value="search_igdb" class="mr-1">
                                            <v-list-item-title class="d-flex"><v-icon icon="mdi-search-web" class="mr-2"/>Search IGDB</v-list-item-title>
                                        </v-list-item>
                                        <v-divider class="mb-2 mt-2"></v-divider>
                                        <v-list-item key="edit" value="edit">
                                            <v-list-item-title class="d-flex"><v-icon icon="mdi-pencil-box" class="mr-2"/>Edit</v-list-item-title>
                                        </v-list-item>
                                        <v-list-item key="scan" value="scan">
                                            <v-list-item-title class="d-flex" @click="scanRom()"><v-icon icon="mdi-magnify-scan" class="mr-2"/>Scan</v-list-item-title>
                                        </v-list-item>
                                        <v-divider class="mb-4 mt-2"></v-divider>
                                        <v-list-item key="delete" value="delete" class="bg-red mb-2">
                                            <v-list-item-title class="d-flex"><v-icon icon="mdi-delete" class="mr-2"/>Delete</v-list-item-title>
                                        </v-list-item>
                                        
                                    </v-list>
                                </v-menu>
                            </v-col>
                        </v-row>
                    </v-container>
                </v-row>
            </v-container>
        </v-col>
        <v-col cols="15" xs="15" sm="12" md="6" lg="10">
            <v-container>
                <v-row>IGDB id: {{ rom.r_igdb_id }}</v-row>
                <v-row>Name: {{ rom.name }}</v-row>
                <v-row>File: {{ rom.filename }}</v-row>
                <v-row>Slug: {{ rom.r_slug }}</v-row>
                <v-row>Platform: {{ rom.p_slug }}</v-row>
                <v-row>Cover: {{ rom.path_cover_l }}</v-row>
                <v-divider v-if="rom.summary != ''" class="mt-8 mb-8"></v-divider>
                <v-row>{{ rom.summary }}</v-row>
            </v-container>
        </v-col>
    </v-row>
    <v-divider class="mt-10 mb-10 border-opacity-75"></v-divider>
</template>