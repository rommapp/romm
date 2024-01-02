function isKeyof<T>(key: PropertyKey, obj: T): key is keyof T {
    return key in obj;
}
