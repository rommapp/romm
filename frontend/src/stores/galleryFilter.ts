import { normalizeString } from "@/utils";
import { defineStore } from "pinia";

export default defineStore("galleryFilter", {
  state: () => ({
    activeFilterDrawer: false,
    activeFirmwareDrawer: false,
    filterSearch: "",
    filters: ["genres", "franchises", "collections", "companies"] as const,
    filterGenres: [] as string[],
    filterFranchises: [] as string[],
    filterCollections: [] as string[],
    filterCompanies: [] as string[],
    filterUnmatched: false,
    selectedGenre: null as string | null,
    selectedFranchise: null as string | null,
    selectedCollection: null as string | null,
    selectedCompany: null as string | null,
  }),

  actions: {
    switchActiveFilterDrawer() {
      this.activeFilterDrawer = !this.activeFilterDrawer;
    },
    switchActiveFirmwareDrawer() {
      this.activeFirmwareDrawer = !this.activeFirmwareDrawer;
    },
    setFilterSearch(filterSearch: string) {
      this.filterSearch = normalizeString(filterSearch);
    },
    setFilterGenre(genres: string[]) {
      this.filterGenres = genres;
    },
    setFilterFranchise(franchises: string[]) {
      this.filterFranchises = franchises;
    },
    setFilterCollection(collections: string[]) {
      this.filterCollections = collections;
    },
    setFilterCompany(companies: string[]) {
      this.filterCompanies = companies;
    },
    setSelectedGenre(genre: string) {
      this.selectedGenre = genre;
    },
    setSelectedFilterFranchise(franchise: string) {
      this.selectedFranchise = franchise;
    },
    setSelectedFilterCollection(collection: string) {
      this.selectedCollection = collection;
    },
    setSelectedFilterCompany(company: string) {
      this.selectedCompany = company;
    },
    switchFilterUnmatched() {
      this.filterUnmatched = !this.filterUnmatched;
    },
    disableFilterUnmatched() {
      this.filterUnmatched = false;
    },
    isFiltered() {
      return Boolean(
        normalizeString(this.filterSearch).trim() != "" ||
          this.filterUnmatched ||
          this.selectedGenre ||
          this.selectedFranchise ||
          this.selectedCollection ||
          this.selectedCompany,
      );
    },
    reset() {
      this.filterGenres = [];
      this.filterFranchises = [];
      this.filterCollections = [];
      this.filterCompanies = [];
      this.selectedGenre = null;
      this.selectedFranchise = null;
      this.selectedCollection = null;
      this.selectedCompany = null;
    },
  },
});
