<template>
    <thead>
        <v-list-item>
            <v-row class="text-subtitle-2">
                <v-col cols="9" xs="9" sm="6" md="3" lg="3"><span>Name</span></v-col>
                <v-col md="4" lg="4" class="hidden-sm-and-down"><span>File</span></v-col>
                <v-col md="1" lg="1" class="hidden-sm-and-down"><span>Platform</span></v-col>
                <v-col xs="2" sm="2" md="2" lg="2" class="hidden-xs"><span>Size</span></v-col>
                <v-col xs="1" sm="1" md="1" lg="1" class="hidden-xs"><span>Region</span></v-col>
                <v-col xs="1" sm="1" md="1" lg="1" class="hidden-xs"><span>Revision</span></v-col>
            </v-row>
            <template v-slot:prepend>
                <v-avatar></v-avatar>
            </template>
            <template v-slot:append>
                <v-btn size="x-small" variant="text"/>
                <v-btn size="x-small" variant="text"/>
                <v-btn size="x-small" variant="text" class="hidden-sm-and-down"/>
            </template>
        </v-list-item>
    </thead>
</template>