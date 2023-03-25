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
        emitter.emit('snackbarScan', {'msg': rom.value.filename+" updated successfully!", 'icon': 'mdi-check-bold', 'color': 'green'})
        rom.value = response.data.data
    }).catch((error) => {
        console.log(error)
        emitter.emit('snackbarScan', {'msg': "Couldn't updated "+rom.value.filename+". Something went wrong...", 'icon': 'mdi-close-circle', 'color': 'red'})
    })
    changing.value = false
}

async function editRom() {
    await axios.patch('/api/platforms/'+rom.value.p_slug+'/roms/'+rom.value.filename, {
        filename: romNewName.value
    }).then((response) => {
        console.log(response)
        console.log("update "+rom.value.filename+" to "+romNewName.value)
        rom.value.filename = romNewName.value
        emitter.emit('snackbarScan', {'msg': romNewName.value+" edited successfully!", 'icon': 'mdi-check-bold', 'color': 'green'})
        dialogEditRom.value = false
    }).catch((error) => {
        console.log(error)
        emitter.emit('snackbarScan', {'msg': error.response.data.detail, 'icon': 'mdi-close-circle', 'color': 'red'})
    })
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
        emitter.emit('snackbarScan', {'msg': "Couldn't delete "+rom.value.filename+". Something went wrong...", 'icon': 'mdi-close-circle', 'color': 'red'})
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
                                            <v-icon icon="mdi-dots-vertical" size="large"/>
                                        </v-btn>
                                    </template>
                                    <v-list rounded="0" class="pa-0">
                                        <v-list-item @click="searchRomIGDB()" class="pt-4 pb-4 pr-5">
                                            <v-list-item-title class="d-flex"><v-icon icon="mdi-search-web" class="mr-2"/>Search IGDB</v-list-item-title>
                                        </v-list-item>
                                        <v-divider class="border-opacity-25"/>
                                        <v-list-item @click="dialogEditRom=true" key="edit" value="edit" class="pt-4 pb-4 pr-5">
                                            <v-list-item-title class="d-flex"><v-icon icon="mdi-pencil-box" class="mr-2"/>Edit</v-list-item-title>
                                        </v-list-item>
                                        <v-divider class="border-opacity-25"/>
                                        <v-list-item key="delete" value="delete" class="pt-4 pb-4 pr-5 bg-red">
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

    <v-dialog v-model="dialogSearchRom" scroll-strategy="none" width="auto" :scrim="false">
        <v-card max-width="600">
            <v-toolbar title="Results found in IGDB:" class="pl-2 pr-8"/>
            <v-list rounded="0" class="pa-0">
                <div clasS="d-flex justify-center"><v-progress-circular v-show="searching" :width="2" :size="20" class="pa-3 ma-3" indeterminate/></div>
                <div v-for="rom in matchedRoms">
                        <v-list-item v-show="!searching" :key="rom" :value="rom" class="pt-4 pb-4 pl-4 pr-4">
                            <v-list-item-title @click="changeRom(rom)" class="d-flex">{{ rom.name }}</v-list-item-title>
                        </v-list-item>
                    </div>
                </v-list>
        </v-card>
    </v-dialog>

    <v-dialog v-model="dialogEditRom" scroll-strategy="none" width="auto" :scrim="false">
        <v-card max-width="600">
            <v-toolbar :title="'Editing '+rom.filename" class="pl-2 pr-8"/>
            <v-card-text class="pt-5">
                <v-form @submit.prevent class="ma-4">
                    <v-text-field @keyup.enter="editRom()" v-model="romNewName" label="File name" variant="outlined"  required/>
                    <v-file-input @keyup.enter="editRom()" label="Custom cover" prepend-inner-icon="mdi-image" prepend-icon="" variant="outlined" disabled/>
                    <v-btn type="submit" @click="editRom()" class="mt-2" block>Apply</v-btn>
                </v-form>
            </v-card-text>
        </v-card>
    </v-dialog>

    <v-dialog v-model="dialogDeleteRom" width="auto">
        <v-expand-transition>
            <v-card max-width="600">
                <v-toolbar :title="'Deleting '+rom.filename" class="pl-2 pr-8" color="red"/>
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

    <v-dialog v-model="changing" scroll-strategy="none" width="auto">
        <v-progress-circular :width="3" :size="70" indeterminate/>
    </v-dialog>

</template>