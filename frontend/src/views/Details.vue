<script setup>
import axios from 'axios'
import { ref, inject } from 'vue'
import { useRouter } from 'vue-router'
import { downloadRom, downloadSave } from '@/utils/utils.js'

// Props
const rom = ref(JSON.parse(localStorage.getItem('currentRom')) || '')
const saveFiles = ref(false)
const searching = ref(false)
const igdb_id = ref('')
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

const selectedPlatform = ref(JSON.parse(localStorage.getItem('selectedPlatform')) || '')

// Event listeners bus
const emitter = inject('emitter')
emitter.on('currentRom', (currentRom) => { rom.value = currentRom })

// Functions
async function searchRomIGDB() {
    searching.value = true
    dialogSearchRom.value = true
    await axios.put('/api/search/roms/igdb?igdb_id='+igdb_id.value, {
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

    <v-card class="bg" position="absolute" rounded="0" flat><v-img :src="'/assets'+rom.path_cover_s+'?reload='+Date.now()" cover class="bg-img"/></v-card>

    <div class="content">
        <v-row class="pt-8 justify-center content">
            <v-col cols="8" xs="3" sm="2" md="2" lg="2" class="cover">
                <v-container class="pa-0" fluid>
                    <v-row>
                        <v-col>
                            <v-card elevation="5">
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
                    <v-row class="pl-3 pr-3">
                        <v-col class="pa-0">
                            <v-btn @click="downloadRom(rom, emitter, filesToDownload)" rounded="0" block><v-icon icon="mdi-download" size="large"/></v-btn>
                        </v-col>
                        <v-col class="pa-0">
                            <v-btn @click="downloadSave(rom, emitter)" rounded="0" block :disabled="!saveFiles"><v-icon icon="mdi-content-save-all" size="large"/></v-btn>
                        </v-col>
                        <v-col class="pa-0">
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
            </v-col>

            <v-col cols="10" xs="8" sm="10" md="10" lg="8" class="info mt-16">

                <div class="info-header text-white">
                    <v-row no-gutters>
                        <p class="text-h4 font-weight-bold">{{ rom.name }}</p>
                        <v-chip-group class="ml-3 mt-1">
                            <v-chip v-show="rom.region" size="x-small" label>{{ rom.region }}</v-chip>
                            <v-chip v-show="rom.revision" size="x-small" label>{{ rom.revision }}</v-chip>
                        </v-chip-group>
                    </v-row>
                    <p class="font-italic mt-1">{{ selectedPlatform['name'] }}</p>
                </div>
                
                <div class="info-content mb-10">
                    <v-row v-if="!rom.multi" class="d-flex align-center mt-0">
                        <v-col cols="3" xs="3" sm="2" md="2" lg="2" class="font-weight-medium"><p>File</p></v-col>
                        <v-col><p>{{ rom.file_name }} MB</p></v-col>
                    </v-row>
                    <v-row v-if="rom.multi" class="d-flex align-center mt-0">
                        <v-col cols="3" xs="3" sm="2" md="2" lg="2" class="font-weight-medium"><p>Files</p></v-col>
                        <v-col><v-select :label="rom.file_name" item-title="file_name" v-model="filesToDownload" :items="rom.files" class="mt-2 mb-2" density="compact" variant="outlined" return-object multiple hide-details clearable chips/></v-col>
                    </v-row>
                    <v-row class="d-flex align-center mt-0">
                        <v-col cols="3" xs="3" sm="2" md="2" lg="2" class="font-weight-medium"><p>Size</p></v-col>
                        <v-col><p>{{ rom.file_size }} MB</p></v-col>
                    </v-row>
                    <v-row class="d-flex align-center mt-0">
                        <v-col cols="3" xs="3" sm="2" md="2" lg="2" class="font-weight-medium"><p>IGDB</p></v-col>
                        <v-col>
                            <v-chip :href="'https://www.igdb.com/games/'+rom.r_slug" label>{{ rom.r_igdb_id }}</v-chip>
                        </v-col>
                    </v-row>
                    <v-row v-if="rom.tags.length>0" class="d-flex align-center mt-0">
                        <v-col cols="3" xs="3" sm="2" md="2" lg="2" class="font-weight-medium"><p>Tags</p></v-col>
                        <v-col><v-chip-group class="pt-0"><v-chip v-for="tag in rom.tags" variant="outlined" label>{{ tag }}</v-chip></v-chip-group></v-col>
                    </v-row>
                    <v-row class="d-flex mt-3">
                        <v-col class="font-weight-medium text-body-2"><p>{{ rom.summary }}</p></v-col>
                    </v-row>
                </div>
            </v-col>
        </v-row>
    </div>    
    
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

            <v-text-field
                @keyup.enter="searchRomIGDB()"
                @click:clear="igdb_id=''"
                v-show="!searching"
                v-model="igdb_id"
                label="search by id"
                prepend-inner-icon="mdi-search-web"
                class="ml-5 mt-5 mr-5 mb-5 shrink"
                variant="outlined"
                density="compact"
                hide-details
                clearable/>

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
.bg {
    top: 0px;
    width: 100%;
    max-height: 330px;
}
.bg-img{
    -webkit-filter: blur(50px);
    filter: blur(50px);
}
.content {
    position: relative;
}
.info-header{
    text-shadow: 1px 1px 3px #000000, 0 0 3px #000000;
}
.info-content{
    margin-top: 105px;
    max-width: 600px;
}
</style>