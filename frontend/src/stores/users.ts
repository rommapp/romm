import { defineStore } from "pinia";
import type { UserSchema } from "@/__generated__";
import i18n from "@/locales";

export type User = UserSchema;

const asciiOnly = (v: string) =>
  // eslint-disable-next-line no-control-regex
  /^[\u0000-\u007F]*$/.test(v) || i18n.global.t("common.ascii-only");

const usernameLength = (v: string) =>
  (v.length >= 3 && v.length <= 255) || i18n.global.t("common.username-length");

const usernameChars = (v: string) =>
  /^[a-zA-Z0-9_-]*$/.test(v) || i18n.global.t("common.username-chars");

const passwordLength = (v: string) =>
  (v.length >= 6 && v.length <= 255) || i18n.global.t("common.password-length");

export default defineStore("users", {
  state: () => ({
    allUsers: [] as User[],
    usernameRules: [
      (v: string) => !!v || i18n.global.t("common.required"),
      asciiOnly,
      usernameLength,
      usernameChars,
    ],
    passwordRules: [
      (v: string) => !!v || i18n.global.t("common.required"),
      asciiOnly,
      passwordLength,
    ],
    emailRules: [
      (v: string) => !!v || i18n.global.t("common.required"),
      (v: string) =>
        /.+@.+\..+/.test(v) || i18n.global.t("common.invalid-email"),
      asciiOnly,
    ],
  }),

  getters: {
    admins: (state) => state.allUsers.filter((user) => user.role === "admin"),
  },

  actions: {
    set(users: User[]) {
      this.allUsers = users;
    },
    add(user: User) {
      this.allUsers = this.allUsers.concat(user);
    },
    update(user: User) {
      this.allUsers = this.allUsers.map((value) => {
        if (value.id === user.id) {
          return user;
        }
        return value;
      });
    },
    remove(userId: number) {
      this.allUsers = this.allUsers.filter((value) => {
        return value.id !== userId;
      });
    },
    reset() {
      this.allUsers = [] as User[];
    },
  },
});
