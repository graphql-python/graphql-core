from graphql.pyutils import RefSet, SetMap


class Member:
    pass


def describe_set_map():
    def maps_exact_sets_regardless_of_insertion_order():
        cache = SetMap[RefSet[Member], int]()
        a = Member()
        b = Member()

        cache[RefSet([a, b])] = 0

        assert cache.get(RefSet([a, b])) == 0
        assert cache.get(RefSet([b, a])) == 0

    def distinguishes_sets_which_share_members():
        cache = SetMap[RefSet[Member], int]()
        a = Member()
        b = Member()
        c = Member()

        cache[RefSet([a, b])] = 0
        cache[RefSet([a, c])] = 1
        cache[RefSet([a, b, c])] = 2
        cache[RefSet([c, b])] = 3

        assert cache.get(RefSet([a, b])) == 0
        assert cache.get(RefSet([a, c])) == 1
        assert cache.get(RefSet([a, b, c])) == 2
        assert cache.get(RefSet([c, b])) == 3

    def maps_the_empty_set():
        cache = SetMap[RefSet[Member], int]()

        assert cache.get(RefSet()) is None
        cache[RefSet()] = 0
        assert cache.get(RefSet()) == 0

    def supports_none_values():
        cache = SetMap[RefSet[Member], None]()
        member = Member()

        cache[RefSet([member])] = None

        assert cache.get(RefSet([member]), 1) is None
        assert RefSet([member]) in cache

    def compares_members_by_identity():
        cache = SetMap[RefSet[list], int]()
        a = [None]
        b = [None]

        cache[RefSet([a])] = 0

        assert RefSet([a]) in cache
        assert RefSet([b]) not in cache

    def iterates_canonical_keys_and_values_in_insertion_order():
        cache = SetMap[RefSet[Member], int]()
        a = Member()
        b = Member()
        first = RefSet([a])
        second = RefSet([a, b])

        cache[first] = 1
        cache[second] = 2
        cache[RefSet([a])] = 3

        assert len(cache) == 2
        assert list(cache.keys()) == [first, second]
        assert next(iter(cache)) is first
        assert list(cache.values()) == [3, 2]
        assert list(cache.items()) == [(first, 3), (second, 2)]

    def can_insert_values_on_demand():
        cache = SetMap[RefSet[Member], int]()
        member = Member()

        assert cache.get_or_insert(RefSet([member]), 0) == 0
        assert cache.get_or_insert(RefSet([member]), 1) == 0

    def can_compute_values_on_demand():
        cache = SetMap[RefSet[Member], int]()
        member = Member()
        calls = []

        def compute(members):
            calls.append(members)
            return 0

        assert cache.get_or_insert_computed(RefSet([member]), compute) == 0
        assert cache.get_or_insert_computed(RefSet([member]), compute) == 0
        assert len(calls) == 1

    def does_not_recreate_none_values():
        cache = SetMap[RefSet[Member], None]()
        member = Member()
        calls = []

        def compute(members):
            calls.append(members)

        assert cache.get_or_insert_computed(RefSet([member]), compute) is None
        assert cache.get_or_insert_computed(RefSet([member]), compute) is None
        assert len(calls) == 1

    def updates_values_inserted_during_computation():
        cache = SetMap[RefSet[Member], int]()
        member = Member()

        def compute(members):
            cache[members] = 1
            return 2

        assert cache.get_or_insert_computed(RefSet([member]), compute) == 2
        assert cache.get(RefSet([member])) == 2

    def can_be_created_with_items_and_deleted_from():
        a = Member()
        first = RefSet([a])
        cache = SetMap[RefSet[Member], int]([(first, 1)])

        assert repr(cache) == f"SetMap([({first!r}, 1)])"
        assert cache[RefSet([a])] == 1
        del cache[RefSet([a])]
        assert not cache
