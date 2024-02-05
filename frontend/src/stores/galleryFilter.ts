import { defineStore } from "pinia";
import { normalizeString } from "@/utils";

export default defineStore("galleryFilter", {
  state: () => ({
    filterSearch: "",
    filters: ["genres", "franchises", "collections", "companies"],
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
    setFilterUnmatched() {
      this.filterUnmatched = !this.filterUnmatched;
    },
    isFiltered() {
      return (
        normalizeString(this.filterSearch).trim() != "" ||
        this.selectedGenre ||
        this.filterFranchises ||
        this.selectedCollection ||
        this.selectedCompany
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
