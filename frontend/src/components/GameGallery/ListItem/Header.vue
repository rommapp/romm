<template>
    <thead>
        <v-row no-gutter>
            <v-col>
                <v-list-item>
                    <v-row class="text-subtitle-2 align-center">
                        <v-col cols="9" xs="9" sm="6" md="3" lg="3"><span>Name</span></v-col>
                        <v-col md="4" lg="4" class="hidden-sm-and-down"><span>File</span></v-col>
                        <v-col md="1" lg="1" class="hidden-sm-and-down"><span>Platform</span></v-col>
                        <v-col sm="2" md="2" lg="2" class="hidden-xs"><span>Size</span></v-col>
                        <v-col sm="1" md="1" lg="1" class="hidden-xs"><span>Reg</span></v-col>
                        <v-col sm="1" md="1" lg="1" class="hidden-xs"><span>Rev</span></v-col>
                    </v-row>
                    <template v-slot:prepend>
                        <v-avatar></v-avatar>
                    </template>
                </v-list-item>
            </v-col>
            <v-col cols="3" xs="3" sm="1" md="1" lg="1" class="d-flex justify-center align-center mr-4">
                <v-btn size="x-small" variant="text"/>
                <v-btn size="x-small" variant="text"/>
                <v-btn size="x-small" variant="text"/>
            </v-col>
        </v-row>
    </thead>
</template>