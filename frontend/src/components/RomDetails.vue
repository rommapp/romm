<script setup>
import axios from 'axios'
import { ref, inject, toRaw } from 'vue'
import { useRouter } from 'vue-router'
import { downloadRom, downloadSave } from '@/utils/utils.js'

// Props
const rom = ref(JSON.parse(localStorage.getItem('currentRom')) || '')
const saveFiles = ref(false)
const searching = ref(false)
const matchedRoms = ref([])
const changing = ref(false)
const romNewName = ref(rom.value.filename)
const snackbarShow = ref(false)
const snackbarStatus = ref({})
const dialogSearchRom = ref(false)
const dialogEditRom = ref(false)
const dialogDeleteRom = ref(false)
const router = useRouter()
// Event listeners bus
const emitter = inject('emitter')
emitter.on('currentRom', (currentRom) => { rom.value = currentRom })

// Functions
async function searchRomIGDB() {
    searching.value = true
    dialogSearchRom.value = true
    console.log("searching for rom... "+rom.value.filename)
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
    searching.value = false
}

async function changeRom(newRomRaw) {
    changing.value = true
    dialogSearchRom.value = false
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
        snackbarStatus.value = {'msg': rom.value.filename+" changed successfully!", 'icon': 'mdi-check-bold', 'color': 'green'}
        rom.value = response.data.data
    }).catch((error) => {
        console.log(error)
        snackbarStatus.value = {'msg': "Couldn't change "+rom.value.filename+". Something went wrong...", 'icon': 'mdi-close-circle', 'color': 'red'}
    })
    snackbarShow.value = true
    changing.value = false
}

async function editRom() {
    await axios.patch('/api/platforms/'+rom.value.p_slug+'/roms/'+rom.value.filename, {
        filename: romNewName.value
    }).then((response) => {
        console.log(response)
        console.log("update "+rom.value.filename+" to "+romNewName.value)
        rom.value.filename = romNewName.value
        snackbarStatus.value = {'msg': romNewName.value+" edited successfully!", 'icon': 'mdi-check-bold', 'color': 'green'}
        dialogEditRom.value = false
    }).catch((error) => {
        console.log(error)
        snackbarStatus.value = {'msg': error.response.data.detail, 'icon': 'mdi-close-circle', 'color': 'red'}
    })
    snackbarShow.value = true
}

async function deleteRom() {
    console.log('deleting rom '+ rom.value.filename)
    await axios.delete('/api/platforms/'+rom.value.p_slug+'/roms/'+rom.value.filename)
    .then((response) => {
        console.log(response)
        emitter.emit('snackbarScan', {'msg': rom.value.filename+" deleted successfully!", 'icon': 'mdi-check-bold', 'color': 'green'})
        router.push(import.meta.env.BASE_URL)
    }).catch((error) => {
        console.log(error)
        snackbarStatus.value = {'msg': "Couldn't delete "+rom.value.filename+". Something went wrong...", 'icon': 'mdi-close-circle', 'color': 'red'}
        snackbarShow.value = true
    })
}
</script>

<template>
    <v-row class="text-body-1 justify-center">
        <v-col cols="8" xs="8" sm="4" md="3" lg="2">
            <v-container class="pa-0" fluid>
                <v-row>
                    <v-col>
                        <v-card >
                            <v-img :src="rom.path_cover_l+'?reload='+Date.now()" :lazy-src="rom.path_cover_s+'?reload='+Date.now()" cover>
                                <template v-slot:placeholder>
                                    <div class="d-flex align-center justify-center fill-height">
                                        <v-progress-circular :width="2" :size="20" indeterminate/>
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
                                <v-btn @click="downloadRom(rom)" rounded="0" block><v-icon icon="mdi-download" size="large"/></v-btn>
                            </v-col>
                            <v-col class="pa-1">
                                <v-btn @click="downloadSave()" rounded="0" block :disabled="!saveFiles"><v-icon icon="mdi-content-save-all" size="large"/></v-btn>
                            </v-col>
                            <v-col class="pa-1">
                                <v-menu location="bottom">
                                    <template v-slot:activator="{ props }">
                                        <v-btn v-bind="props" rounded="0" block>
                                            <v-icon v-show="!changing" icon="mdi-dots-vertical" size="large"/>
                                            <v-progress-circular v-show="changing" :width="2" :size="20" indeterminate/>
                                        </v-btn>
                                    </template>
                                    <v-list rounded="0">
                                        <v-list-item @click="searchRomIGDB()">
                                            <v-list-item-title class="d-flex"><v-icon icon="mdi-search-web" class="mr-2"/>Search IGDB</v-list-item-title>
                                        </v-list-item>
                                        <v-divider class="mb-2 mt-2"/>
                                        <v-list-item @click="dialogEditRom=true" key="edit" value="edit">
                                            <v-list-item-title class="d-flex"><v-icon icon="mdi-pencil-box" class="mr-2"/>Edit</v-list-item-title>
                                        </v-list-item>
                                        
                                        <v-divider class="mb-4 mt-2"/>
                                        <v-list-item key="delete" value="delete" class="bg-red mb-2">
                                            <v-list-item-title @click="dialogDeleteRom=true" class="d-flex"><v-icon icon="mdi-delete" class="mr-2"/>Delete</v-list-item-title>
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
                <v-divider v-if="rom.summary != ''" class="mt-8 mb-8"/>
                <v-row>{{ rom.summary }}</v-row>
            </v-container>
        </v-col>
    </v-row>
    
    <v-divider class="mt-10 mb-10 border-opacity-75"/>

    <v-dialog v-model="dialogSearchRom" width="auto" :scrim="false">
        <v-card width="550">
            <v-toolbar :title="'Results found for '+rom.filename" class="pt-2 pb-2 pl-4 pr-8"/>
            <v-card-text class="pt-5 justify-center">
                <v-list rounded="0">
                    <v-list-item v-show="searching">
                        <v-progress-circular :width="2" :size="20" class="pa-2" indeterminate/>
                    </v-list-item>
                    <v-list-item v-for="rom in matchedRoms" v-show="!searching"  :key="rom" :value="rom">
                        <v-list-item-title @click="changeRom(rom)" class="d-flex">{{ rom.name }}</v-list-item-title>
                    </v-list-item>
                </v-list>
            </v-card-text>
        </v-card>
    </v-dialog>

    <v-dialog v-model="dialogEditRom" width="auto" :scrim="false">
        <v-card width="550">
            <v-toolbar :title="'Editing '+rom.filename" class="pt-2 pb-2 pl-4 pr-8"/>
            <v-card-text class="pt-5">
                <v-form @submit.prevent class="ma-4">
                    <v-text-field @keyup.enter="editRom()" v-model="romNewName" label="File name" variant="outlined"  required/>
                    <v-file-input @keyup.enter="editRom()" label="Custom cover" prepend-icon="mdi-image" variant="outlined" disabled/>
                    <v-btn type="submit" @click="editRom()" class="mt-2" block>Apply</v-btn>
                </v-form>
            </v-card-text>
        </v-card>
    </v-dialog>

    <v-dialog v-model="dialogDeleteRom" width="auto">
        <v-expand-transition>
            <v-card>
                <v-toolbar :title="'Deleting '+rom.filename" class="pa-2" color="red"/>
                <v-card-text class="pt-5 pr-10 pl-10">
                <div class="text-body-1">This action can't be reversed. Do you confirm?</div>
                </v-card-text>
                <v-card-actions class="justify-center pb-6 pt-3 pr-3 pl-3">
                    <v-btn @click="deleteRom()" class="bg-red mr-5">Confirm</v-btn>
                    <v-btn @click="dialogDeleteRom=false" variant="tonal">Cancel</v-btn>
                </v-card-actions>
            </v-card>
        </v-expand-transition>
    </v-dialog>

    <v-snackbar v-model="snackbarShow" :timeout="4000" location="top" class="mt-4">
        <v-icon :icon="snackbarStatus.icon" :color="snackbarStatus.color" class="ml-2 mr-2"/>
        {{ snackbarStatus.msg }}
        <template v-slot:actions>
            <v-btn variant="text" @click="snackbarShow = false"><v-icon icon="mdi-close"/></v-btn>
        </template>
    </v-snackbar>

</template>