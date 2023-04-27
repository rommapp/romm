<script setup>
import axios from 'axios'
import { ref, inject, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDisplay } from "vuetify"
import { downloadRom, downloadSave } from '@/services/download.js'
import { storeDownloader } from '@/stores/downloader.js'
import BackgroundHeader from '@/components/GameDetails/BackgroundHeader.vue'
import AppBar from '@/components/AppBar/Base.vue'

const router = useRouter()
const route = useRoute()

// Props
const rom = ref(undefined)
const updatedRom = ref(undefined)
const saveFiles = ref(false)
const searching = ref(false)
const searchTerm = ref('')
const searchBy = ref('Name')
const matchedRoms = ref([])
const updating = ref(false)
const loading = ref(true)
const renameAsIGDB = ref(false)
const dialogSearchRom = ref(false)
const dialogEditRom = ref(false)
const dialogDeleteRom = ref(false)
const deleteFromFs = ref(false)
const filesToDownload = ref([])
const downloader = storeDownloader()
const tab = ref('info')
const { xs, sm, mdAndUp, mdAndDown, smAndDown } = useDisplay()

// Event listeners bus
const emitter = inject('emitter')

// Functions
async function searchRomIGDB() {
    searching.value = true
    dialogSearchRom.value = true
    await axios.put('/api/search/roms/igdb?search_term='+searchTerm.value+'&search_by='+searchBy.value, {
        rom: rom.value
    }).then((response) => {
        matchedRoms.value = response.data.data
    }).catch((error) => {console.log(error)})
    searching.value = false
}

async function updateRom(updatedData={...updatedRom.value}) {
    dialogSearchRom.value = false
    updating.value = true
    updatedRom.value.r_igdb_id = updatedData.r_igdb_id
    updatedRom.value.r_slug = updatedData.r_slug
    updatedRom.value.summary = updatedData.summary
    updatedRom.value.url_cover = updatedData.url_cover
    updatedRom.value.url_screenshots = updatedData.url_screenshots
    updatedRom.value.r_name = updatedData.r_name
    if (renameAsIGDB.value) { updatedRom.value.file_name = updatedRom.value.file_name.replace(updatedRom.value.file_name_no_tags, updatedData.r_name) }
    await axios.patch('/api/platforms/'+rom.value.p_slug+'/roms/'+rom.value.id, { updatedRom: updatedRom.value }).then((response) => {
        rom.value = response.data.data
        updatedRom.value = {...response.data.data}
        emitter.emit('snackbarScan', {'msg': response.data.msg, 'icon': 'mdi-check-bold', 'color': 'green'})
        router.push('/platform/'+rom.value.p_slug+'/rom/'+rom.value.id)
    }).catch((error) => {
        emitter.emit('snackbarScan', {'msg': error.response.data.detail, 'icon': 'mdi-close-circle', 'color': 'red'})
    })
    renameAsIGDB.value = false
    updating.value = false
    dialogEditRom.value = false
}

async function deleteRom() {
    await axios.delete('/api/platforms/'+rom.value.p_slug+'/roms/'+rom.value.id+'?filesystem='+deleteFromFs.value)
    .then((response) => {
        emitter.emit('snackbarScan', {'msg': response.data.msg, 'icon': 'mdi-check-bold', 'color': 'green'})
        router.push('/platform/'+rom.value.p_slug)
    }).catch((error) => {
        console.log(error)
        emitter.emit('snackbarScan', {'msg': error.response.data.detail, 'icon': 'mdi-close-circle', 'color': 'red'})
        if (error.response.status == 404) { router.push('/platform/'+rom.value.p_slug) }
    })
    dialogDeleteRom.value = false
}

async function rescan() { console.log("rescan "+rom.value.id) }

onMounted(() => {
    axios.get(`/api/platforms/${route.params.platform}/roms/${route.params.rom}`).then(response => {
        rom.value = response.data.data
        updatedRom.value = {...response.data.data}
        loading.value = false
    }).catch((error) => { console.log(error);loading.value = false })
})
</script>

<template>

    <app-bar class="app-bar-test" v-if="smAndDown"/>

    <background-header :rom="rom" v-if="rom !== undefined"/>

    <div :class="{'content': mdAndUp, 'content-tablet': sm, 'content-mobile': xs}" v-if="rom !== undefined">
        <v-row class="pt-8 justify-center">

            <v-col :class="{'cover': mdAndUp, 'cover-tablet': sm, 'cover-mobile': xs}">
                    <v-row>
                        <v-col>
                            <v-card elevation="5" :loading="downloader.value.includes(rom.file_name) ? 'rommAccent1': null">
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
                    <v-row class="pl-3 pr-3 action-buttons">
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
                        <span class="text-h4 font-weight-bold rom-name">{{ rom.r_name }}</span>
                        <v-chip-group class="ml-3 mt-1 hidden-xs">
                            <v-chip v-show="rom.region" size="x-small" class="bg-chip" label>{{ rom.region }}</v-chip>
                            <v-chip v-show="rom.revision" size="x-small" class="bg-chip" label>{{ rom.revision }}</v-chip>
                        </v-chip-group>
                    </v-row> 
                    <v-row no-gutters class="align-center">
                        <span class="font-italic mt-1 rom-platform">{{ rom.p_name || rom.p_slug }}</span>
                        <v-chip-group class="ml-3 mt-1 hidden-sm-and-up">
                            <v-chip v-show="rom.region" size="x-small" class="bg-chip" label>{{ rom.region }}</v-chip>
                            <v-chip v-show="rom.revision" size="x-small" class="bg-chip" label>{{ rom.revision }}</v-chip>
                        </v-chip-group>
                    </v-row>
                </div>
                
                <div :class="{'info-content': mdAndUp, 'info-content-tablet': sm, 'info-content-mobile': xs}">
                    <v-tabs v-model="tab" slider-color="rommAccent1" >
                        <v-tab value="info" rounded="0">Info</v-tab>
                        <v-tab value="saves" rounded="0" disabled>Saves<span class="text-caption text-truncate ml-1">[comming soon]</span></v-tab>
                        <v-tab v-if="rom.path_screenshots.length>0" value="screenshots" rounded="0">Screenshots</v-tab>
                    </v-tabs>
                    <v-window v-model="tab" class="mt-2">
                        <v-window-item value="info">
                            <v-row v-if="!rom.multi" class="d-flex align-center text-body-1 mt-0">
                                <v-col cols="3" xs="3" sm="2" md="2" lg="2" class="font-weight-medium"><span>File</span></v-col>
                                <v-col class="text-body-1"><span>{{ rom.file_name }}</span></v-col>
                            </v-row>
                            <v-row v-if="rom.multi" class="d-flex align-center text-body-1 mt-0">
                                <v-col cols="3" xs="3" sm="2" md="2" lg="2" class="font-weight-medium"><span>Files</span></v-col>
                                <v-col><v-select :label="rom.file_name" item-title="file_name" v-model="filesToDownload" :items="rom.files" class="mt-2 mb-2" density="compact" variant="outlined" return-object multiple hide-details clearable chips/></v-col>
                            </v-row>
                            <v-row class="d-flex align-center text-body-1 mt-0">
                                <v-col cols="3" xs="3" sm="2" md="2" lg="2" class="font-weight-medium"><span>Size</span></v-col>
                                <v-col><span>{{ rom.file_size }} {{ rom.file_size_units }}</span></v-col>
                            </v-row>
                            <v-row v-if="rom.r_igdb_id!=''" class="d-flex align-center text-body-1 mt-0">
                                <v-col cols="3" xs="3" sm="2" md="2" lg="2" class="font-weight-medium"><span>IGDB</span></v-col>
                                <v-col>
                                    <v-chip variant="outlined" :href="'https://www.igdb.com/games/'+rom.r_slug" label>{{ rom.r_igdb_id }}</v-chip>
                                </v-col>
                            </v-row>
                            <v-row v-if="rom.tags.length>0" class="d-flex align-center text-body-1 mt-0">
                                <v-col cols="3" xs="3" sm="2" md="2" lg="2" class="font-weight-medium"><span>Tags</span></v-col>
                                <v-col><v-chip-group class="pt-0"><v-chip v-for="tag in rom.tags" :key="tag" class="bg-chip" label>{{ tag }}</v-chip></v-chip-group></v-col>
                            </v-row>
                            <v-row class="d-flex mt-3">
                                <v-col class="font-weight-medium text-caption"><p>{{ rom.summary }}</p></v-col>
                            </v-row>
                        </v-window-item>
                        <v-window-item value="screenshots">
                            <v-row class="d-flex mt-2">
                                <v-carousel hide-delimiter-background delimiter-icon="mdi-square" class="bg-rommBlack" show-arrows="hover" height="400">
                                    <v-carousel-item v-for="screenshot in rom.path_screenshots" :src="'/assets'+screenshot"/>
                                </v-carousel>
                            </v-row>
                        </v-window-item>
                        <v-window-item value="saves">
                            <v-row class="d-flex mt-2">
                                <v-col></v-col>
                            </v-row>
                        </v-window-item>
                    </v-window>
                </div>
            </v-col>

        </v-row>
    </div>
    
    <v-dialog v-model="dialogSearchRom" scroll-strategy="none" width="auto" :scrim="false" v-if="rom !== undefined">
        <v-card :class="{'search-content': mdAndUp, 'search-content-tablet': sm, 'search-content-mobile': xs}">

            <v-toolbar class="pb-1 pt-1 bg-primary" density="compact">
                <v-chip class="ml-3 text-rommAccent1" variant="outlined" label>IGDB</v-chip>
                <v-toolbar-title v-show="searching">Searching...</v-toolbar-title>
                <v-toolbar-title v-show="!searching">Results found</v-toolbar-title>
                <v-btn icon @click="dialogSearchRom=false" class="ml-1" rounded="0"><v-icon>mdi-close</v-icon></v-btn>
            </v-toolbar>

            <v-divider class="border-opacity-25" :thickness="1"/>
            
            <v-toolbar density="compact" class="bg-secondary pt-1 pb-1">
                <v-row class="align-center">
                    <v-col class="pb-1 pr-1 pl-6 pt-1" cols="6" xs="8" sm="8" md="8" lg="8">
                        <v-text-field
                            @keyup.enter="searchRomIGDB()"
                            @click:clear="searchTerm=''"
                            v-model="searchTerm"
                            label="search"
                            variant="outlined"
                            density="compact"
                            hide-details
                            clearable/>
                    </v-col>
                    <v-col class="pb-1 pl-1 pr-1 pt-1" cols="3" xs="2" sm="2" md="2" lg="2">
                        <v-select variant="outlined" density="compact" label="by" :items="['ID', 'Name']" v-model="searchBy" hide-details/>
                    </v-col>
                    <v-col class="pb-1 pl-1 pr-6 pt-1" cols="3" xs="2" sm="2" md="2" lg="2">
                        <v-btn type="submit" @click="searchRomIGDB()" class="bg-primary" block cover><v-icon icon="mdi-search-web"/>{{ mdAndUp ? 'Search' : '' }}</v-btn>
                    </v-col>
                </v-row>
            </v-toolbar>
            <v-card-text class="pa-0 pl-3 pr-3 scroll justify-center align-center bg-secondary">
                <v-row class="justify-center align-center loader-searching" v-show="searching"><v-progress-circular :width="2" :size="40" class="pa-3 ma-3" color="rommAccent1" indeterminate/></v-row>
                <v-row class="justify-center align-center no-results-searching" v-show="!searching && matchedRoms.length==0" ><span>No results found</span></v-row>
                <v-row class="pl-2 pr-2 pb-2 mt-0">
                    <v-col class="pa-1" cols="4" xs="4" sm="3" md="2" lg="2" v-show="!searching" v-for="rom in matchedRoms" :key="rom.file_name">
                        <v-hover v-slot="{isHovering, props}">
                            <v-card @click="updateRom(updatedData=rom)" v-bind="props" :class="{'on-hover': isHovering}" :elevation="isHovering ? 20 : 3">
                                <v-img v-bind="props" :src="rom.url_cover" cover/>
                                <v-card-text>
                                    <v-row class="pa-1">
                                        <span class="d-inline-block text-truncate">{{ rom.r_name }}</span>
                                    </v-row>
                                </v-card-text>
                            </v-card>
                        </v-hover>
                    </v-col>
                </v-row>
            </v-card-text>

            <v-divider v-show="!searching" class="border-opacity-25" :thickness="1"/>

            <v-toolbar class="bg-primary pt-1 pb-1" density="compact" v-show="!searching">
                <v-checkbox v-model="renameAsIGDB" label="Rename file" class="ml-3" hide-details="true"/>
            </v-toolbar>

        </v-card>
    </v-dialog>

    <v-dialog v-model="dialogEditRom" scroll-strategy="none" width="auto" :scrim="false" v-if="rom !== undefined">
        <v-card rounded="0" :class="{'edit-content': mdAndUp, 'edit-content-tablet': sm, 'edit-content-mobile': xs}">
            <v-toolbar class="bg-primary pt-1 pb-1" density="compact">
                <v-toolbar-title><span>Editing</span></v-toolbar-title>
                <v-btn icon @click="dialogEditRom=false" class="ml-1" rounded="0"><v-icon>mdi-close</v-icon></v-btn>
            </v-toolbar>

            <v-divider class="border-opacity-25" :thickness="1"/>

            <v-card-text class="bg-secondary">
                <v-form @submit.prevent class="ma-4">
                    <v-text-field @keyup.enter="updateRom()" v-model="updatedRom.file_name" label="File name" variant="outlined" required/>
                    <v-file-input @keyup.enter="updateRom()" label="Custom cover [Comming soon]" prepend-inner-icon="mdi-image" prepend-icon="" variant="outlined" disabled/>
                </v-form>
                <v-row class="justify-center mb-2">
                    <v-btn type="submit" @click="updateRom()" class="bg-rommGreen">Apply</v-btn>
                    <v-btn @click="dialogEditRom=false" class="ml-5" variant="tonal">Cancel</v-btn>
                </v-row>
            </v-card-text>
        </v-card>
    </v-dialog>
    
    <v-dialog v-model="dialogDeleteRom" width="auto" v-if="rom !== undefined">
        <v-card rounded="0" :class="{'delete-content': mdAndUp, 'delete-content-tablet': sm, 'delete-content-mobile': xs}">
            <v-toolbar class="bg-red pt-1 pb-1" density="compact">
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
            
            <v-toolbar class="bg-primary pt-1 pb-1" density="compact">
                <v-checkbox v-model="deleteFromFs" label="Remove from filesystem" class="ml-3" hide-details="true"/>
            </v-toolbar>
        </v-card>
    </v-dialog>

    <v-dialog :model-value="updating || loading" scroll-strategy="none" width="auto" :scrim="updating" persistent>
        <v-progress-circular :width="3" :size="70" color="rommAccent1" indeterminate/>
    </v-dialog>
    
</template>

<style scoped>
.app-bar-test{
    position: absolute;
}
.scroll {
    overflow-y: scroll
}
.content{
    position: absolute !important;
    margin-top: 64px;
    margin-left: 100px;
    margin-right: 100px;
}
.content-tablet{
    margin-top: 64px;
    margin-left: 20px;
    margin-right: 20px;
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
    margin-top: 54px;
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
    width: 900px;
    height: 640px;
}
.search-content-tablet{
    width: 550px;
    height: 550px;
}
.search-content-mobile{
    width: 85vw;
    height: 620px;
}
.edit-content{
    width: 700px;
}
.edit-content-tablet{
    width: 500px;
}
.edit-content-mobile{
    width: 85vw;
}
.delete-content{
    width: 700px;
}
.delete-content-tablet{
    width: 500px;
}
.delete-content-mobile{
    width: 85vw;
}
</style>
