import { defineStore } from "pinia";
import type { PlatformSchema } from "@/__generated__";
import { romStatusMap } from "@/utils";

export type Platform = PlatformSchema;

export type FilterType =
  | "genre"
  | "franchise"
  | "collection"
  | "company"
  | "ageRating"
  | "status"
  | "region"
  | "language";

const defaultFilterState = {
  activeFilterDrawer: false,
  searchTerm: null as string | null,
  filterPlatforms: [] as Platform[],
  filterGenres: [] as string[],
  filterFranchises: [] as string[],
  filterCollections: [] as string[],
  filterCompanies: [] as string[],
  filterAgeRatings: [] as string[],
  filterRegions: [] as string[],
  filterLanguages: [] as string[],
  filterStatuses: Object.values(romStatusMap).map((status) => status.text),
  filterUnmatched: false,
  filterMatched: false,
  filterFavorites: false,
  filterDuplicates: false,
  filterPlayables: false,
  filterRA: false,
  filterMissing: false,
  filterVerified: false,
  selectedPlatform: null as Platform | null,
  selectedGenre: null as string | null,
  selectedFranchise: null as string | null,
  selectedCollection: null as string | null,
  selectedCompany: null as string | null,
  selectedAgeRating: null as string | null,
  selectedRegion: null as string | null,
  selectedLanguage: null as string | null,
  selectedStatus: null as string | null,
};

export default defineStore("galleryFilter", {
  state: () => ({ ...defaultFilterState }),

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
    setFilterRegions(regions: string[]) {
      this.filterRegions = regions;
    },
    setFilterLanguages(languages: string[]) {
      this.filterLanguages = languages;
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
    setSelectedFilterRegion(region: string) {
      this.selectedRegion = region;
    },
    setSelectedFilterLanguage(language: string) {
      this.selectedLanguage = language;
    },
    setSelectedFilterStatus(status: string) {
      this.selectedStatus = status;
    },
    setFilterUnmatched(value: boolean) {
      this.filterUnmatched = value;
      this.filterMatched = false;
    },
    switchFilterUnmatched() {
      this.filterUnmatched = !this.filterUnmatched;
      this.filterMatched = false;
    },
    setFilterMatched(value: boolean) {
      this.filterMatched = value;
      this.filterUnmatched = false;
    },
    switchFilterMatched() {
      this.filterMatched = !this.filterMatched;
      this.filterUnmatched = false;
    },
    setFilterFavorites(value: boolean) {
      this.filterFavorites = value;
    },
    switchFilterFavorites() {
      this.filterFavorites = !this.filterFavorites;
    },
    setFilterDuplicates(value: boolean) {
      this.filterDuplicates = value;
    },
    switchFilterDuplicates() {
      this.filterDuplicates = !this.filterDuplicates;
    },
    setFilterPlayables(value: boolean) {
      this.filterPlayables = value;
    },
    switchFilterPlayables() {
      this.filterPlayables = !this.filterPlayables;
    },
    setFilterRA(value: boolean) {
      this.filterRA = value;
    },
    switchFilterRA() {
      this.filterRA = !this.filterRA;
    },
    setFilterMissing(value: boolean) {
      this.filterMissing = value;
    },
    switchFilterMissing() {
      this.filterMissing = !this.filterMissing;
    },
    setFilterVerified(value: boolean) {
      this.filterVerified = value;
    },
    switchFilterVerified() {
      this.filterVerified = !this.filterVerified;
    },
    isFiltered() {
      return Boolean(
        this.filterUnmatched ||
          this.filterMatched ||
          this.filterFavorites ||
          this.filterDuplicates ||
          this.filterPlayables ||
          this.filterRA ||
          this.filterMissing ||
          this.filterVerified ||
          this.selectedPlatform ||
          this.selectedGenre ||
          this.selectedFranchise ||
          this.selectedCollection ||
          this.selectedCompany ||
          this.selectedAgeRating ||
          this.selectedRegion ||
          this.selectedLanguage ||
          this.selectedStatus,
      );
    },
    reset() {
      Object.assign(this, { ...defaultFilterState });
    },
    resetFilters() {
      this.selectedPlatform = null;
      this.selectedGenre = null;
      this.selectedFranchise = null;
      this.selectedCollection = null;
      this.selectedCompany = null;
      this.selectedAgeRating = null;
      this.selectedRegion = null;
      this.selectedLanguage = null;
      this.selectedStatus = null;
      this.filterUnmatched = false;
      this.filterMatched = false;
      this.filterFavorites = false;
      this.filterDuplicates = false;
      this.filterPlayables = false;
      this.filterRA = false;
      this.filterMissing = false;
      this.filterVerified = false;
    },
  },
});
