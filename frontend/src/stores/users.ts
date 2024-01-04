import { defineStore } from "pinia";
import type { UserSchema } from "@/__generated__";

export type User = UserSchema;

export default defineStore("users", {
    state: () => ({
        all: [] as User[],
    }),

    getters: {
        admins: (state) => state.all.filter((user) => user.role === "admin"),
    },

    actions: {
        set(users: User[]) {
            this.all = users;
        },
        add(user: User) {
            this.all = this.all.concat(user);
        },
        update(user: User) {
            this.all = this.all.map((value) => {
                if (value.id === user.id) {
                    return user;
                }
                return value;
            })
        },
        remove(userId: number) {
            this.all = this.all.filter((value) => {
                return value.id !== userId;
            })
        },
        reset() {
            this.all = [];
        }
    }
});
