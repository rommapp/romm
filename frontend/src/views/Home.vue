<script setup>
import { ref } from 'vue'
import { useDisplay } from "vuetify"
import { views } from '@/utils/utils.js'
import Platform from '@/components/Home/Platform.vue'
import { storePlatforms } from '@/stores/platforms.js'

// Props
const platforms = storePlatforms()
const totalGames = ref(platforms.value.reduce((count, p) => { return count + p.n_roms }, 0))
const { lgAndUp } = useDisplay()
</script>

<template>

        <v-row id="home-header-logo" class="pa-2" no-gutters>
            <v-spacer/>
            <v-col cols="12" xs="12" sm="10" md="10" lg="10">
                <v-img :height="lgAndUp ? 200 : 150" src="/assets/romm_complete.svg" cover />
            </v-col>
            <v-spacer/>
        </v-row>

        <v-row id="home-chips" class="pa-2" no-gutters>
            <v-spacer/>
            <v-col cols="12" xs="12" sm="10" md="10" lg="10" class="d-flex justify-center">
                <v-chip-group>
                    <v-chip class="bg-chip" label>
                        <span class="text-overline">{{ platforms.value.length }} platforms</span>
                    </v-chip>
                    <v-chip class="bg-chip" label>
                        <span class="text-overline">{{ totalGames }} games</span>
                    </v-chip>
                </v-chip-group>
            </v-col>
            <v-spacer/>
        </v-row>

        <v-row id="platforms-title" class="pa-2" no-gutters>
            <v-avatar :rounded="0" size="auto"><v-icon>mdi-controller</v-icon></v-avatar>
            <span class="text-h6 ml-2">Platforms</span>
            <v-divider class="border-opacity-25"/>
        </v-row>

        <v-row id="platforms-cards" class="pa-2" no-gutters>
            <v-col v-for="platform in platforms.value" class="pa-1" :key="platform.slug"
                :cols="views[0]['size-cols']" :xs="views[0]['size-xs']" :sm="views[0]['size-sm']" :md="views[0]['size-md']" :lg="views[0]['size-lg']">
                <platform :platform="platform" :key="platform.slug"/>
            </v-col>
        </v-row>
    
</template>
