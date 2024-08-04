import { normalizeString } from "@/utils";
import { defineStore } from "pinia";

const filters = ["genres", "franchises", "collections", "companies"] as const;

export type FilterType = (typeof filters)[number];

export default defineStore("galleryFilter", {
  state: () => ({
    activeFilterDrawer: false,
    filterSearch: "",
    filters: filters,
    filterGenres: [] as string[],
    filterFranchises: [] as string[],
    filterCollections: [] as string[],
    filterCompanies: [] as string[],
    filterUnmatched: false,
    filterFavourites: false,
    filterDuplicates: false,
    selectedGenre: null as string | null,
    selectedFranchise: null as string | null,
    selectedCollection: null as string | null,
    selectedCompany: null as string | null,
  }),

  actions: {
    switchActiveFilterDrawer() {
      this.activeFilterDrawer = !this.activeFilterDrawer;
    },
    setFilterSearch(filterSearch: string) {
      this.filterSearch = normalizeString(filterSearch);
    },
    setFilterGenres(genres: string[]) {
      this.filterGenres = genres;
    },
    setFilterFranchises(franchises: string[]) {
      this.filterFranchises = franchises;
    },
    setFilterCollections(collections: string[]) {
      this.filterCollections = collections;
    },
    setFilterCompanies(companies: string[]) {
      this.filterCompanies = companies;
    },
    setSelectedFilterGenre(genre: string) {
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
    switchFilterFavourites() {
      this.filterFavourites = !this.filterFavourites;
    },
    disableFilterFavourites() {
      this.filterFavourites = false;
    },
    switchFilterDuplicates() {
      this.filterDuplicates = !this.filterDuplicates;
    },
    disableFilterDuplicates() {
      this.filterDuplicates = false;
    },
    isFiltered() {
      return Boolean(
        normalizeString(this.filterSearch).trim() != "" ||
          this.filterUnmatched ||
          this.filterFavourites ||
          this.filterDuplicates ||
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
