<script setup>
import { ref } from 'vue'
import { useDisplay } from "vuetify"
import { views } from '@/utils/utils.js'
import Platform from '@/components/Home/Platform.vue'
import { storePlatforms } from '@/stores/platforms.js'

const platforms = storePlatforms()
const totalGames = ref(platforms.value.reduce((count, p) => { return count + p.n_roms }, 0))
const { lgAndUp } = useDisplay()
</script>

<template>
    <v-col>
        <v-card class="mx-auto mt-10" max-width="1000" variant="text">
            <v-img :height="lgAndUp ? 220 : 95" src="/assets/romm_complete.svg" cover />
        </v-card>

        <v-row class="ml-2 mt-6" no-gutters>
            <v-avatar :rounded="0" size="auto"><v-icon>mdi-controller</v-icon></v-avatar>
            <span class="text-h6 ml-2">Platforms</span>
        </v-row>

        <v-row class="pa-1" no-gutters>
            <v-col v-for="platform in platforms.value" class="pa-1" :key="platform.slug" :cols="views[1]['size-cols']"
                :xs="views[1]['size-xs']" :sm="views[1]['size-sm']" :md="views[1]['size-md']" :lg="views[1]['size-lg']">
                <platform :platform="platform" :key="platform.slug" />
            </v-col>
        </v-row>

        <v-row no-gutters class="mt-4">
            <v-chip class="ma-2" label>
                <span class="text-overline">{{ platforms.value.length }} platforms</span>
            </v-chip>
            <v-chip class="ma-2" label>
                <span class="text-overline">{{ totalGames }} games</span>
            </v-chip>
        </v-row>
    </v-col>
</template>
