import { defineStore } from "pinia";

export type User = {
    id: number
    username: string
    enabled: boolean
    role: "viewer" | "editor" | "admin"
    oauth_scopes: string[]
    avatar_path: string
}

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
