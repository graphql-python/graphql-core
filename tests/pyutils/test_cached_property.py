from graphql.pyutils import cached_property


def describe_cached_property():
    def works_like_a_normal_property():
        class TestClass:
            @cached_property
            def value(self):
                return 42

        assert TestClass().value == 42

    def caches_the_value():
        class TestClass:
            evaluations = 0

            @cached_property
            def value(self):
                self.__class__.evaluations += 1
                return 42

        obj = TestClass()
        assert TestClass.evaluations == 0
        assert obj.value == 42
        assert TestClass.evaluations == 1
        assert obj.value == 42
        assert TestClass.evaluations == 1
