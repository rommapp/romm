<script setup>
import axios from 'axios'
import { ref, inject, toRaw } from "vue";

// Props
const rom = ref("")
const scanOverwrite = ref(false)
rom.value = JSON.parse(localStorage.getItem('currentRom')) || ''
const matchedRoms = ref([])
const searching = ref(false)
const changing = ref(false)
const romFilename = ref(rom.value.filename)
const submitted = ref(false)

// Event listeners bus
const emitter = inject('emitter')
emitter.on('currentRom', (currentRom) => { rom.value = currentRom })

// Functions
async function searchRomIGDB() {
    searching.value = true
    console.log("searching for rom... "+rom.value.filename)
    if(matchedRoms.value.length == 0){
        await axios.put('/api/search/roms/igdb', {
            filename: rom.value.filename,
            p_igdb_id: rom.value.p_igdb_id
        }).then((response) => {
            console.log(response.data.data)
            if (response.data.data.length != 0){
                matchedRoms.value = response.data.data
            }else{
                matchedRoms.value = [{'name': 'No games found'}]
            }
        }).catch((error) => {console.log(error)})
    }
    searching.value = false
}

async function changeRom(newRomRaw) {
    changing.value = true
    const newRom = toRaw(newRomRaw)
    newRom.filename = rom.value.filename
    console.log(newRom)
    await axios.patch('/api/platforms/'+rom.value.p_slug+'/roms/'+rom.value.filename, {
        filename: rom.value.filename,
        r_igdb_id: newRom.id,
        p_igdb_id: rom.value.p_igdb_id
    }).then((response) => {
        console.log("update "+rom.value.filename+" completed")
        localStorage.setItem('currentRom', JSON.stringify(response.data.data))
        rom.value = response.data.data
    }).catch((error) => {console.log(error)})
    changing.value = false
}

async function submitEdit() {
    submitted.value = true
    await axios.patch('/api/platforms/'+rom.value.p_slug+'/roms/'+rom.value.filename, {
        filename: romFilename.value
    }).then((response) => {
        console.log("update "+rom.value.filename+" to "+romFilename.value)
        rom.value.filename = romFilename.value
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
                            <v-img :src="rom.path_cover_l+'?reload='+Date.now()" :lazy-src="rom.path_cover_s+'?reload='+Date.now()" cover>
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
                                        <v-btn rounded="0" block v-bind="props">
                                            <v-icon size="large" v-show="!changing" icon="mdi-dots-vertical"/>
                                            <v-progress-circular v-show="changing" indeterminate color="primary" :width="2" :size="20" class="ml-2"/>
                                        </v-btn>
                                    </template>
                                    <v-list rounded="0">
                                        <v-menu location="end">
                                            <template v-slot:activator="{ props }">
                                                <v-list-item key="search_igdb" value="search_igdb" @click="searchRomIGDB()" v-bind="props">
                                                    <v-list-item-title class="d-flex"><v-icon icon="mdi-search-web" class="mr-2"/>
                                                        Search IGDB
                                                        <v-progress-circular v-show="searching" indeterminate color="primary" :width="2" :size="20" class="ml-2"/>
                                                    </v-list-item-title>
                                                </v-list-item>
                                            </template>
                                            <v-list rounded="0">
                                                <v-list-item v-for="rom in matchedRoms" :key="rom" :value="rom">
                                                    <v-list-item-title class="d-flex" @click="changeRom(rom)">{{ rom.name }}</v-list-item-title>
                                                </v-list-item>
                                            </v-list>
                                        </v-menu>
                                        <v-divider class="mb-2 mt-2"></v-divider>
                                        <v-menu location="end" :close-on-content-click="false" min-width="290px">
                                            <template v-slot:activator="{ props }">
                                                <v-list-item key="edit" value="edit" v-bind="props">
                                                    <v-list-item-title class="d-flex"><v-icon icon="mdi-pencil-box" class="mr-2"/>Edit</v-list-item-title>
                                                </v-list-item>
                                            </template>
                                            <v-list rounded="0">
                                                <v-form @submit.prevent class="ma-4">
                                                    <v-text-field v-model="romFilename" label="File name" variant="outlined" required @keyup.enter="submitEdit()"/>
                                                    <v-file-input prepend-icon="mdi-image" label="Cover L" variant="outlined"/>
                                                    <v-file-input prepend-icon="mdi-image" label="Cover S" variant="outlined"/>
                                                    <v-btn type="submit" class="mt-2" @click="submitEdit()" block>Submit<v-icon v-if="submitted" icon="mdi-check-bold" color="green" class="ml-2"/></v-btn>
                                                </v-form>
                                            </v-list>
                                        </v-menu>
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