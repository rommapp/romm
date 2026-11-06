from collections.abc import Hashable, Iterable


def sibling_groups(key_rows: Iterable[tuple[int, Hashable]]) -> dict[int, int]:
    """Group ROMs that are linked through any chain of shared identity keys.

    Args:
        key_rows: (rom id, identity key) pairs, one per key a ROM holds.

    Returns:
        Each ROM's group id (its group's lowest ROM id), for ROMs in a group
        of two or more only.
    """
    parent: dict[int, int] = {}

    def find(rom_id: int) -> int:
        root = parent.setdefault(rom_id, rom_id)
        while root != parent[root]:
            # Path halving keeps a long chain from making every lookup linear.
            parent[root] = parent[parent[root]]
            root = parent[root]
        return root

    key_owner: dict[Hashable, int] = {}
    for rom_id, key in key_rows:
        find(rom_id)
        owner = key_owner.setdefault(key, rom_id)
        left, right = find(owner), find(rom_id)
        if left != right:
            # The lower id wins, so a root is always its group's lowest member.
            parent[max(left, right)] = min(left, right)

    roots = {rom_id: find(rom_id) for rom_id in parent}
    sizes: dict[int, int] = {}
    for root in roots.values():
        sizes[root] = sizes.get(root, 0) + 1
    return {rom_id: root for rom_id, root in roots.items() if sizes[root] > 1}
