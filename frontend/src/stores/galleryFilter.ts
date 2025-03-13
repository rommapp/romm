import type { PlatformSchema } from "@/__generated__";
import { romStatusMap } from "@/utils";
import { defineStore } from "pinia";

export type Platform = PlatformSchema;

const filters = [
  "genres",
  "franchises",
  "meta_collections",
  "companies",
  "age_ratings",
  "status",
] as const;

const statusFilters = Object.values(romStatusMap).map((status) => status.text);

export type FilterType = (typeof filters)[number];

const defaultFilterState = {
  activeFilterDrawer: false,
  searchText: null as string | null,
  filterText: null as string | null,
  filters: filters,
  filterPlatforms: [] as Platform[],
  filterGenres: [] as string[],
  filterFranchises: [] as string[],
  filterCollections: [] as string[],
  filterCompanies: [] as string[],
  filterAgeRatings: [] as string[],
  filterStatuses: statusFilters,
  filterUnmatched: false,
  filterMatched: false,
  filterFavourites: false,
  filterDuplicates: false,
  selectedPlatform: null as Platform | null,
  selectedGenre: null as string | null,
  selectedFranchise: null as string | null,
  selectedCollection: null as string | null,
  selectedCompany: null as string | null,
  selectedAgeRating: null as string | null,
  selectedStatus: null as string | null,
};

export default defineStore("galleryFilter", {
  state: () => defaultFilterState,

  actions: {
    switchActiveFilterDrawer() {
      this.activeFilterDrawer = !this.activeFilterDrawer;
    },
    setFilterPlatforms(platforms: Platform[]) {
      this.filterPlatforms = platforms;
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
    setFilterAgeRatings(ageRatings: string[]) {
      this.filterAgeRatings = ageRatings;
    },
    setSelectedFilterPlatform(platform: Platform) {
      this.selectedPlatform = platform
        ? this.filterPlatforms.find((p) => p.id === platform.id) || null
        : null;
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
    setSelectedFilterAgeRating(ageRating: string) {
      this.selectedAgeRating = ageRating;
    },
    setSelectedFilterStatus(status: string) {
      this.selectedStatus = status;
    },
    switchFilterUnmatched() {
      this.filterUnmatched = !this.filterUnmatched;
      this.filterMatched = false;
    },
    disableFilterUnmatched() {
      this.filterUnmatched = false;
    },
    switchFilterMatched() {
      this.filterMatched = !this.filterMatched;
      this.filterUnmatched = false;
    },
    disableFilterMatched() {
      this.filterMatched = false;
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
        this.filterUnmatched ||
          this.filterMatched ||
          this.filterFavourites ||
          this.filterDuplicates ||
          this.selectedPlatform ||
          this.selectedGenre ||
          this.selectedFranchise ||
          this.selectedCollection ||
          this.selectedCompany ||
          this.selectedAgeRating ||
          this.selectedStatus,
      );
    },
    reset() {
      Object.assign(this, defaultFilterState);
    },
  },
});
