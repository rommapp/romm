import { defineStore } from "pinia";
import type { UserSchema } from "@/__generated__";
//import { useI18n } from "vue-i18n";

//const { t } = useI18n();
export type User = UserSchema;

export default defineStore("users", {
  state: () => ({
    allUsers: [] as User[],
    nameRules: [
      (v: string) => !!v || "common.required",
      (v: string) =>
        /* trunk-ignore(eslint/no-useless-escape) */
        /^[a-zA-Z0-9-_\\\./\|]+$/.test(v) ||
        "Name can't contain special characters",
    ],
    passwordRules: [(v: string) => !!v || "common.required"],
    emailRules: [
      (v: string) => !!v || "common.required",
      (v: string) => /.+@.+\..+/.test(v) || "common.invalidEmail",
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
