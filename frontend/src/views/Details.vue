<script setup>
import axios from 'axios'
import { ref, inject } from 'vue'
import { useRouter } from 'vue-router'
import { downloadRom, downloadSave } from '@/utils/utils.js'

// Props
const rom = ref(JSON.parse(localStorage.getItem('currentRom')) || '')
const saveFiles = ref(false)
const searching = ref(false)
const matchedRoms = ref([])
const updating = ref(false)
const editedRomName = ref(rom.value.file_name)
const renameAsIGDB = ref(false)
const dialogSearchRom = ref(false)
const dialogEditRom = ref(false)
const dialogDeleteRom = ref(false)
const deleteFromFs = ref(false)
const router = useRouter()
const filesToDownload = ref([])

// Event listeners bus
const emitter = inject('emitter')
emitter.on('currentRom', (currentRom) => { rom.value = currentRom })

// Functions
async function searchRomIGDB() {
    searching.value = true
    dialogSearchRom.value = true
    await axios.put('/api/search/roms/igdb', {
        rom: rom.value
    }).then((response) => {
        matchedRoms.value = response.data.data
    }).catch((error) => {console.log(error)})
    searching.value = false
}

async function updateRom(updatedRom=Object.assign({},rom.value), newName=rom.value.file_name) {
    updating.value = true
    dialogSearchRom.value = false
    if (renameAsIGDB.value) {
        updatedRom.file_name = rom.value.file_name.replace(rom.value.file_name_no_tags.trim(), updatedRom.name)
        editedRomName.value = updatedRom.file_name
        renameAsIGDB.value = false
    }
    else{
        updatedRom.file_name = newName
    }
    await axios.patch('/api/platforms/'+rom.value.p_slug+'/roms', {
        rom: rom.value,
        updatedRom: updatedRom
    }).then((response) => {
        localStorage.setItem('currentRom', JSON.stringify(response.data.data))
        emitter.emit('snackbarScan', {'msg': rom.value.file_name+" updated successfully!", 'icon': 'mdi-check-bold', 'color': 'green'})
        rom.value = response.data.data
    }).catch((error) => {
        console.log(error)
        emitter.emit('snackbarScan', {'msg': "Couldn't updated "+rom.value.file_name+". Something went wrong...", 'icon': 'mdi-close-circle', 'color': 'red'})
    })
    updating.value = false
    dialogEditRom.value = false
}

async function deleteRom() {
    await axios.delete('/api/platforms/'+rom.value.p_slug+'/roms/'+rom.value.file_name+'?filesystem='+deleteFromFs.value)
    .then((response) => {
        emitter.emit('snackbarScan', {'msg': rom.value.file_name+" deleted successfully!", 'icon': 'mdi-check-bold', 'color': 'green'})
        router.push(import.meta.env.BASE_URL)
    }).catch((error) => {
        console.log(error)
        emitter.emit('snackbarScan', {'msg': "Couldn't delete "+rom.value.file_name+". Something went wrong...", 'icon': 'mdi-close-circle', 'color': 'red'})
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
                            <v-img :src="'/assets'+rom.path_cover_l+'?reload='+Date.now()" :lazy-src="'/assets'+rom.path_cover_s+'?reload='+Date.now()" cover>
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
                                <v-btn
                                    @click="downloadRom(rom, emitter, filesToDownload)"
                                    rounded="0"
                                    block>
                                    <v-icon
                                        icon="mdi-download"
                                        size="large"/>
                                </v-btn>
                            </v-col>
                            <v-col class="pa-1">
                                <v-btn @click="downloadSave(rom, emitter)" rounded="0" block :disabled="!saveFiles"><v-icon icon="mdi-content-save-all" size="large"/></v-btn>
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
                                        <v-list-item @click="dialogEditRom=true" class="pt-4 pb-4 pr-5">
                                            <v-list-item-title class="d-flex"><v-icon icon="mdi-pencil-box" class="mr-2"/>Edit</v-list-item-title>
                                        </v-list-item>
                                        <v-divider class="border-opacity-25"/>
                                        <v-list-item @click="dialogDeleteRom=true" class="pt-4 pb-4 pr-5 bg-red">
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
            <v-table density="comfortable">
                <tbody>
                    <tr><td>Name</td><td>{{ rom.name }}</td></tr>
                    <tr v-show="!rom.multi"><td>File</td><td>{{ rom.file_name }}</td></tr>
                    <tr v-show="rom.multi"><td>Files</td><td>
                        <v-select :label="rom.file_name" item-title="file_name" v-model="filesToDownload" :items="rom.files" class="mt-2 mb-2" density="compact" variant="outlined" return-object multiple hide-details clearable chips/>
                    </td></tr>
                    <tr><td>Platform</td><td>{{ rom.p_slug }}</td></tr>
                    <tr><td>Size</td><td>{{ rom.file_size }} MB</td></tr>
                    <tr><td>IGDB id</td><td><a :href="'https://www.igdb.com/games/'+rom.r_slug">{{ rom.r_igdb_id }}</a></td></tr>
                    <tr v-show="rom.region"><td>Region</td><td>{{ rom.region }}</td></tr>
                    <tr v-show="rom.revision"><td>Revision</td><td>{{ rom.revision }}</td></tr>
                    <tr v-show="rom.tags.length>0"><td>Tags</td><td><v-chip-group><v-chip v-for="tag in rom.tags" label>{{ tag }}</v-chip></v-chip-group></td></tr>
                    <tr><td>Summary</td><td class="pt-3">{{ rom.summary }}</td></tr>
                </tbody>
            </v-table>
        </v-col>
    </v-row>
    
    <v-dialog v-model="dialogSearchRom" scroll-strategy="none" width="auto" :scrim="false">
        <v-card max-width="600">
            <v-toolbar v-show="searching">
                <v-toolbar-title>Searching...</v-toolbar-title>
                <v-btn icon @click="dialogSearchRom=false" class="ml-1" rounded="0"><v-icon>mdi-close</v-icon></v-btn>
            </v-toolbar>
            <v-toolbar v-show="!searching">
                <v-toolbar-title>Results found</v-toolbar-title>
                <v-btn icon @click="dialogSearchRom=false" class="ml-1" rounded="0"><v-icon>mdi-close</v-icon></v-btn>
            </v-toolbar>
            <v-card-text rounded="0" class="pa-3 scroll">
                <div class="d-flex justify-center">
                    <v-progress-circular v-show="searching" :width="2" :size="40" class="pa-3 ma-3" indeterminate/>
                </div>
                <v-row v-show="!searching" class="pa-4">
                    <p v-show="matchedRoms.length==0">No results found</p>
                    <v-col v-for="rom in matchedRoms">
                        <v-hover v-slot="{isHovering, props}">
                            <v-card @click="updateRom(rom, undefined)" v-bind="props" :class="{'on-hover': isHovering}" :elevation="isHovering ? 20 : 3" min-width="100" max-width="140">
                                <v-img v-bind="props" :src="rom.url_cover" cover/>
                                <v-card-text>
                                    <v-row class="pa-2">{{ rom.name }}</v-row>
                                </v-card-text>
                            </v-card>
                        </v-hover>
                    </v-col>
                </v-row>
            </v-card-text>
            <v-card-actions v-show="!searching">
                <v-checkbox v-model="renameAsIGDB" label="Rename file" class="pl-3" hide-details="true"/>
            </v-card-actions>
        </v-card>
    </v-dialog>

    <v-dialog v-model="updating" scroll-strategy="none" width="auto" persistent>
        <v-progress-circular :width="3" :size="70" indeterminate/>
    </v-dialog>

    <v-dialog v-model="dialogEditRom" scroll-strategy="none" width="auto" :scrim="false">
        <v-card max-width="600" min-width="340">
            <v-toolbar>
                <v-toolbar-title>Editing {{ rom.file_name }}</v-toolbar-title>
                <v-btn icon @click="dialogEditRom=false" class="ml-1" rounded="0"><v-icon>mdi-close</v-icon></v-btn>
            </v-toolbar>
            <v-card-text class="pt-5">
                <v-form @submit.prevent class="ma-4">
                    <v-text-field @keyup.enter="updateRom()" v-model="editedRomName" label="File name" variant="outlined" required/>
                    <v-file-input @keyup.enter="updateRom()" label="Custom cover" prepend-inner-icon="mdi-image" prepend-icon="" variant="outlined" disabled/>
                    <v-btn type="submit" @click="updateRom(undefined, editedRomName)" class="mt-2" block>Apply</v-btn>
                </v-form>
            </v-card-text>
        </v-card>
    </v-dialog>

    <v-dialog v-model="dialogDeleteRom" width="auto">
        <v-card max-width="600">
            <v-toolbar class="bg-red">
                <v-toolbar-title>Deleting {{ rom.file_name }}</v-toolbar-title>
                <v-btn icon @click="dialogDeleteRom=false" class="ml-1" rounded="0"><v-icon>mdi-close</v-icon></v-btn>
            </v-toolbar>
            <v-card-text class="pt-5 pr-10 pl-10">
                <div class="text-body-1">Deleting from RomM. Do you confirm?</div>
            </v-card-text>
            <v-card-actions class="justify-center pt-3 pr-3 pl-3">
                <v-btn @click="deleteRom()" class="bg-red mr-5">Confirm</v-btn>
                <v-btn @click="dialogDeleteRom=false" variant="tonal">Cancel</v-btn>
            </v-card-actions>
            <div class="pl-8">
                <v-checkbox v-model="deleteFromFs" label="Remove from filesystem" hide-details="true"/>
            </div>
        </v-card>
    </v-dialog>

</template>

<style scoped>
.scroll {
   overflow-y: scroll
}
</style>