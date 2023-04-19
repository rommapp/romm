<script setup>
import axios from 'axios'
import { ref, inject, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDisplay } from "vuetify"
import { downloadRom, downloadSave } from '@/utils/utils.js'
import BackgroundHeader from '@/components/GameDetails/BackgroundHeader.vue'

const router = useRouter()
const route = useRoute()

// Props
const rom = ref(undefined)
const saveFiles = ref(false)
const searching = ref(false)
const igdb_id = ref('')
const matchedRoms = ref([])
const updating = ref(false)
const loading = ref(true)
const editedRomName = ref(undefined)
const renameAsIGDB = ref(false)
const dialogSearchRom = ref(false)
const dialogEditRom = ref(false)
const dialogDeleteRom = ref(false)
const deleteFromFs = ref(false)
const filesToDownload = ref([])
const tab = ref('info')
const { xs, sm, mdAndUp } = useDisplay()

// Event listeners bus
const emitter = inject('emitter')

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
    dialogSearchRom.value = false
    updating.value = true
    if (renameAsIGDB.value) {
        updatedRom.file_name = rom.value.file_name.replace(rom.value.file_name_no_tags.trim(), updatedRom.r_name)
        editedRomName.value = updatedRom.file_name
        renameAsIGDB.value = false
    }
    else{ updatedRom.file_name = newName }

    await axios.patch('/api/platforms/'+rom.value.p_slug+'/roms/'+rom.value.id, {
        updatedRom: updatedRom
    }).then((response) => {
        emitter.emit('snackbarScan', {'msg': rom.value.file_name+" updated successfully!", 'icon': 'mdi-check-bold', 'color': 'green'})
        // rom.value = response.data.data
        router.push('/'+rom.value.p_slug+'/roms/'+rom.value.file_name)
    }).catch((error) => {
        console.log(error)
        emitter.emit('snackbarScan', {'msg': "Couldn't updated "+rom.value.file_name+". Something went wrong...", 'icon': 'mdi-close-circle', 'color': 'red'})
    })

    updating.value = false
    dialogEditRom.value = false
}

async function deleteRom() {
    await axios.delete('/api/platforms/'+rom.value.p_slug+'/roms/'+rom.value.id+'?filesystem='+deleteFromFs.value)
    .then((response) => {
        emitter.emit('snackbarScan', {'msg': rom.value.file_name+" deleted successfully!", 'icon': 'mdi-check-bold', 'color': 'green'})
        router.push('/')
    }).catch((error) => {
        console.log(error)
        emitter.emit('snackbarScan', {'msg': "Couldn't delete "+rom.value.file_name+". Something went wrong...", 'icon': 'mdi-close-circle', 'color': 'red'})
    })
}

onMounted(() => {
    axios.get(`/api/platforms/${route.params.platform}/roms/${route.params.rom}`).then(response => {
        rom.value = response.data.data
        editedRomName.value = rom.value.file_name
        loading.value = false
    }).catch(error => {
        loading.value = false
    })
})
</script>

<template>

    <background-header :rom="rom" v-if="rom !== undefined"/>

    <div :class="{'content': mdAndUp, 'content-tablet': sm, 'content-mobile': xs}" v-if="rom !== undefined">
        <v-row class="pt-8 justify-center">

            <v-col :class="{'cover': mdAndUp, 'cover-tablet': sm, 'cover-mobile': xs}">
                    <v-row>
                        <v-col>
                            <v-card class="hidden-md-and-down" elevation="5">
                                <v-img :src="'/assets'+rom.path_cover_l+'?reload='+Date.now()" :lazy-src="'/assets'+rom.path_cover_s+'?reload='+Date.now()" cover>
                                    <template v-slot:placeholder>
                                        <div class="d-flex align-center justify-center fill-height">
                                            <v-progress-circular color="rommAccent1" :width="2" :size="20" indeterminate/>
                                        </div> 
                                    </template>
                                </v-img>
                            </v-card>
                            <v-card class="hidden-lg-and-up" elevation="5">
                                <v-img :src="'/assets'+rom.path_cover_l+'?reload='+Date.now()" :lazy-src="'/assets'+rom.path_cover_s+'?reload='+Date.now()" cover>
                                    <template v-slot:placeholder>
                                        <div class="d-flex align-center justify-center fill-height">
                                            <v-progress-circular color="rommAccent1" :width="2" :size="20" indeterminate/>
                                        </div>
                                    </template>
                                </v-img>
                            </v-card>
                        </v-col>
                    </v-row>
                    <v-row class="pl-3 pr-3">
                        <v-col class="pa-0">
                            <v-btn @click="downloadRom(rom, emitter, filesToDownload)" rounded="0" color="primary" block><v-icon icon="mdi-download" size="large"/></v-btn>
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
                                    <v-list-item  @click="searchRomIGDB()" class="pt-4 pb-4 pr-5">
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
            </v-col>

            <v-col class="mt-10" :class="{'info': mdAndUp, 'info-tablet': sm, 'info-mobile': xs}">
                <div class="info-header text-white">
                    <v-row no-gutters>
                        <p class="text-h4 font-weight-bold rom-name">{{ rom.r_name }}</p>
                        <v-chip-group class="ml-3 mt-1 hidden-xs">
                            <v-chip v-show="rom.region" size="x-small" class="bg-chip" label>{{ rom.region }}</v-chip>
                            <v-chip v-show="rom.revision" size="x-small" class="bg-chip" label>{{ rom.revision }}</v-chip>
                        </v-chip-group>
                    </v-row> 
                    <v-row no-gutters class="align-center">
                        <p class="font-italic mt-1 rom-platform">{{ rom.p_name || rom.p_slug }}</p>
                        <v-chip-group class="ml-3 mt-1 hidden-sm-and-up">
                            <v-chip v-show="rom.region" size="x-small" class="bg-chip" label>{{ rom.region }}</v-chip>
                            <v-chip v-show="rom.revision" size="x-small" class="bg-chip" label>{{ rom.revision }}</v-chip>
                        </v-chip-group>
                    </v-row>
                </div>
                
                <div class="mb-10" :class="{'info-content': mdAndUp, 'info-content-tablet': sm, 'info-content-mobile': xs}">
                    <v-tabs v-model="tab" slider-color="rommAccent1">
                        <v-tab value="info">Info</v-tab>
                        <v-tab value="saves" disabled>Saves</v-tab>
                        <v-tab value="screenshots" disabled>Screenshots</v-tab>
                    </v-tabs>
                    <v-window v-model="tab" class="mt-2">
                        <v-window-item value="info">
                            <v-row v-if="!rom.multi" class="d-flex align-center text-body-1 mt-0">
                                <v-col cols="3" xs="3" sm="2" md="2" lg="2" class="font-weight-medium"><p>File</p></v-col>
                                <v-col class="text-body-1"><p>{{ rom.file_name }}</p></v-col>
                            </v-row>
                            <v-row v-if="rom.multi" class="d-flex align-center text-body-1 mt-0">
                                <v-col cols="3" xs="3" sm="2" md="2" lg="2" class="font-weight-medium"><p>Files</p></v-col>
                                <v-col><v-select :label="rom.file_name" item-title="file_name" v-model="filesToDownload" :items="rom.files" class="mt-2 mb-2" density="compact" variant="outlined" return-object multiple hide-details clearable chips/></v-col>
                            </v-row>
                            <v-row class="d-flex align-center text-body-1 mt-0">
                                <v-col cols="3" xs="3" sm="2" md="2" lg="2" class="font-weight-medium"><p>Size</p></v-col>
                                <v-col><p>{{ rom.file_size }} {{ rom.file_size_units }}</p></v-col>
                            </v-row>
                            <v-row v-if="rom.r_igdb_id!=''" class="d-flex align-center text-body-1 mt-0">
                                <v-col cols="3" xs="3" sm="2" md="2" lg="2" class="font-weight-medium"><p>IGDB</p></v-col>
                                <v-col>
                                    <v-chip variant="outlined" :href="'https://www.igdb.com/games/'+rom.r_slug" label>{{ rom.r_igdb_id }}</v-chip>
                                </v-col>
                            </v-row>
                            <v-row v-if="rom.tags.length>0" class="d-flex align-center text-body-1 mt-0">
                                <v-col cols="3" xs="3" sm="2" md="2" lg="2" class="font-weight-medium"><p>Tags</p></v-col>
                                <v-col><v-chip-group class="pt-0"><v-chip v-for="tag in rom.tags" :key="tag" class="bg-chip" label>{{ tag }}</v-chip></v-chip-group></v-col>
                            </v-row>
                            <v-row class="d-flex mt-3">
                                <v-col class="font-weight-medium text-caption"><p>{{ rom.summary }}</p></v-col>
                            </v-row>
                        </v-window-item>
                        <v-window-item value="saves">
                            <v-row class="d-flex mt-2"></v-row>
                        </v-window-item>
                        <v-window-item value="screenshots">
                            <v-row class="d-flex mt-2">
                                <v-col class="font-weight-medium text-caption"><p>{{ rom.summary }}</p></v-col>
                            </v-row>
                        </v-window-item>
                    </v-window>
                </div>
            </v-col>

        </v-row>
    </div>
    
    <v-dialog v-model="dialogSearchRom" scroll-strategy="none" width="auto" :scrim="false" v-if="rom !== undefined">
        <v-card :class="{'search-content': mdAndUp, 'search-content-tablet': sm, 'search-content-mobile': xs}">

            <v-toolbar class="bg-primary" density="compact">
                <v-toolbar-title v-show="searching">Searching...</v-toolbar-title>
                <v-toolbar-title v-show="!searching"><span>Results found</span></v-toolbar-title>
                <v-btn icon @click="dialogSearchRom=false" class="ml-1" rounded="0"><v-icon>mdi-close</v-icon></v-btn>
            </v-toolbar>

            <v-divider class="border-opacity-25" :thickness="1"/>
            
            <v-card-text class="pa-3 scroll justify-center align-center bg-secondary">
                <v-row>
                    <v-text-field
                        @keyup.enter="searchRomIGDB()"
                        @click:clear="igdb_id=''"
                        v-show="!searching"
                        v-model="igdb_id"
                        label="search by id"
                        prepend-inner-icon="mdi-search-web"
                        class="ml-5 mt-5 mr-5 mb-5 "
                        variant="outlined"
                        density="compact"
                        hide-details
                        clearable/>
                </v-row>
                <v-row class="justify-center align-center loader-searching" v-show="searching"><v-progress-circular :width="2" :size="40" class="pa-3 ma-3" color="rommAccent1" indeterminate/></v-row>
                <v-row class="justify-center align-center no-results-searching" v-show="!searching && matchedRoms.length==0" ><p>No results found</p></v-row>
                <v-row class="pl-4 pr-4">
                    <v-col cols="6" xs="6" sm="4" md="3" lg="3" v-show="!searching" v-for="rom in matchedRoms" :key="rom.file_name">
                        <v-hover v-slot="{isHovering, props}">
                            <v-card @click="updateRom(rom, undefined)" v-bind="props" :class="{'on-hover': isHovering}" :elevation="isHovering ? 20 : 3">
                                <v-img v-bind="props" :src="rom.url_cover" cover/>
                                <v-card-text>
                                    <v-row class="pa-2">
                                        <span class="d-inline-block text-truncate">{{ rom.r_name }}</span>
                                    </v-row>
                                </v-card-text>
                            </v-card>
                        </v-hover>
                    </v-col>
                </v-row>
            </v-card-text>

            <v-divider v-show="!searching" class="border-opacity-25" :thickness="1"/>

            <v-card-actions v-show="!searching">
                <v-checkbox v-model="renameAsIGDB" label="Rename file" class="ml-3" hide-details="true"/>
            </v-card-actions>

        </v-card>
    </v-dialog>

    <v-dialog v-model="dialogEditRom" scroll-strategy="none" width="auto" :scrim="false" v-if="rom !== undefined">
        <v-card rounded="0" :class="{'edit-content': mdAndUp, 'edit-content-tablet': sm, 'edit-content-mobile': xs}">
            <v-toolbar class="bg-primary" density="compact">
                <v-toolbar-title><span>Editing {{ rom.file_name }}</span></v-toolbar-title>
                <v-btn icon @click="dialogEditRom=false" class="ml-1" rounded="0"><v-icon>mdi-close</v-icon></v-btn>
            </v-toolbar>

            <v-divider class="border-opacity-25" :thickness="1"/>

            <v-card-text class="bg-secondary">
                <v-form @submit.prevent class="ma-4">
                    <v-text-field @keyup.enter="updateRom()" v-model="editedRomName" label="File name" variant="outlined" required/>
                    <v-file-input @keyup.enter="updateRom()" label="Custom cover" prepend-inner-icon="mdi-image" prepend-icon="" variant="outlined" disabled/>
                </v-form>
                <v-row class="justify-center mb-2">
                    <v-btn type="submit" @click="updateRom(undefined, editedRomName)" class="bg-rommGreen">Apply</v-btn>
                    <v-btn @click="dialogEditRom=false" class="ml-5" variant="tonal">Cancel</v-btn>
                </v-row>
            </v-card-text>
        </v-card>
    </v-dialog>
    
    <v-dialog v-model="dialogDeleteRom" width="auto" v-if="rom !== undefined">
        <v-card rounded="0" max-width="600">
            <v-toolbar class="bg-red" density="compact">
                <v-toolbar-title><span>Deleting {{ rom.file_name }}</span></v-toolbar-title>
                <v-btn icon @click="dialogDeleteRom=false" class="ml-1" rounded="0"><v-icon>mdi-close</v-icon></v-btn>
            </v-toolbar>

            <v-divider class="border-opacity-25" :thickness="1"/>

            <v-card-text class="bg-secondary">
                <v-row class="justify-center ma-2">
                    <span>Deleting from RomM. Do you confirm?</span>
                </v-row>
                <v-row class="justify-center ma-2 mt-5">
                    <v-btn @click="deleteRom()" class="bg-red">Confirm</v-btn>
                    <v-btn @click="dialogDeleteRom=false" class="ml-5" variant="tonal">Cancel</v-btn>
                </v-row>
            </v-card-text>

            <v-divider class="border-opacity-25" :thickness="1"/>
            
            <v-card-actions class="justify-center">
                <v-checkbox v-model="deleteFromFs" label="Remove from filesystem" class="ml-3" hide-details="true"/>
            </v-card-actions>
        </v-card>
    </v-dialog>

    <v-dialog :model-value="updating || loading" scroll-strategy="none" width="auto" :scrim="updating" persistent>
        <v-progress-circular :width="3" :size="70" color="rommAccent1" indeterminate/>
    </v-dialog>
    
</template>

<style scoped>
.scroll {
    overflow-y: scroll
}
.content, .content-tablet{
    margin-left: 100px;
    margin-right: 100px;
}
.content, .content-tablet, .content-mobile {
    position: relative;
}
.cover, .cover-tablet, .cover-mobile {
    min-width: 245px;
    min-height: 326px;
    max-width: 245px;
    max-height: 326px;
}
.info, .info-tablet, .info-mobile {
    padding-left: 25px;
    padding-right: 25px;
}
.rom-name, .rom-platform {
    text-shadow: 1px 1px 3px #000000, 0 0 3px #000000;
}
.info-content{
    margin-top: 110px;
    max-width: 700px;
}
.info-content-tablet {
    margin-top: 70px;
    max-width: 700px;
}
.info-content-mobile{
    margin-top: 40px;
}
.loader-searching {
    margin-top: 200px;
}
.no-results-searching {
    margin-top: 150px;
}
.search-content{
    width: 700px;
    height: 540px;
}
.search-content-tablet{
    width: 500px;
    height: 540px;
}
.search-content-mobile{
    width: 310px;
    height: 540px;
}
.edit-content{
    width: 700px;
    /* height: 540px; */
}
.edit-content-tablet{
    width: 500px;
    /* height: 540px; */
}
.edit-content-mobile{
    width: 310px;
    /* height: 540px; */
}
</style>