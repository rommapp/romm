import { defineStore } from "pinia";
import type { UserSchema } from "@/__generated__";

export type User = UserSchema;

export default defineStore("users", {
  state: () => ({
    allUsers: [] as User[],
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
      this.allUsers = [];
    },
  },
});
