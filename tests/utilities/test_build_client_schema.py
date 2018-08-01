from pytest import raises

from graphql import graphql_sync
from graphql.language import DirectiveLocation
from graphql.type import (
    GraphQLArgument, GraphQLBoolean, GraphQLDirective, GraphQLEnumType,
    GraphQLEnumValue, GraphQLField, GraphQLFloat, GraphQLID,
    GraphQLInputField, GraphQLInputObjectType, GraphQLInt,
    GraphQLInterfaceType, GraphQLList, GraphQLNonNull, GraphQLObjectType,
    GraphQLScalarType, GraphQLSchema, GraphQLString, GraphQLUnionType)
from graphql.utilities import build_client_schema, introspection_from_schema


def check_schema(server_schema):
    """Test that the client side introspection gives the same result.

    Given a server's schema, a client may query that server with introspection,
    and use the result to produce a client-side representation of the schema
    by using "build_client_schema". If the client then runs the introspection
    query against the client-side schema, it should get a result identical to
    what was returned by the server.
    """
    initial_introspection = introspection_from_schema(server_schema)
    client_schema = build_client_schema(initial_introspection)
    second_introspection = introspection_from_schema(client_schema)
    assert initial_introspection == second_introspection


def describe_type_system_build_schema_from_introspection():

    def builds_a_simple_schema():
        schema = GraphQLSchema(GraphQLObjectType('Simple', {
            'string': GraphQLField(
                GraphQLString, description='This is a string field')},
            description='This is a simple type'))
        check_schema(schema)

    def builds_a_simple_schema_with_all_operation_types():
        query_type = GraphQLObjectType('QueryType', {
            'string': GraphQLField(
                GraphQLString, description='This is a string field.')},
            description='This is a simple query type')

        mutation_type = GraphQLObjectType('MutationType', {
            'setString': GraphQLField(
                GraphQLString, description='Set the string field', args={
                    'value': GraphQLArgument(GraphQLString)})},
            description='This is a simple mutation type')

        subscription_type = GraphQLObjectType('SubscriptionType', {
            'string': GraphQLField(
                GraphQLString, description='This is a string field')},
            description='This is a simple subscription type')

        schema = GraphQLSchema(query_type, mutation_type, subscription_type)
        check_schema(schema)

    def uses_built_in_scalars_when_possible():
        custom_scalar = GraphQLScalarType(
            'CustomScalar', serialize=lambda: None)

        schema = GraphQLSchema(GraphQLObjectType('Scalars', {
            'int': GraphQLField(GraphQLInt),
            'float': GraphQLField(GraphQLFloat),
            'string': GraphQLField(GraphQLString),
            'boolean': GraphQLField(GraphQLBoolean),
            'id': GraphQLField(GraphQLID),
            'custom': GraphQLField(custom_scalar)}))

        check_schema(schema)

        introspection = introspection_from_schema(schema)
        client_schema = build_client_schema(introspection)

        # Built-ins are used
        assert client_schema.get_type('Int') is GraphQLInt
        assert client_schema.get_type('Float') is GraphQLFloat
        assert client_schema.get_type('String') is GraphQLString
        assert client_schema.get_type('Boolean') is GraphQLBoolean
        assert client_schema.get_type('ID') is GraphQLID

        # Custom are built
        assert client_schema.get_type('CustomScalar') is not custom_scalar

    def builds_a_schema_with_a_recursive_type_reference():
        recur_type = GraphQLObjectType(
            'Recur', lambda: {'recur': GraphQLField(recur_type)})
        schema = GraphQLSchema(recur_type)

        check_schema(schema)

    def builds_a_schema_with_a_circular_type_reference():
        dog_type = GraphQLObjectType(
            'Dog', lambda: {'bestFriend': GraphQLField(human_type)})
        human_type = GraphQLObjectType(
            'Human', lambda: {'bestFriend': GraphQLField(dog_type)})
        schema = GraphQLSchema(GraphQLObjectType('Circular', {
            'dog': GraphQLField(dog_type),
            'human': GraphQLField(human_type)}))

        check_schema(schema)

    def builds_a_schema_with_an_interface():
        friendly_type = GraphQLInterfaceType('Friendly', lambda: {
            'bestFriend': GraphQLField(
                friendly_type,
                description='The best friend of this friendly thing.')})
        dog_type = GraphQLObjectType('DogType', lambda: {
            'bestFriend': GraphQLField(friendly_type)}, interfaces=[
            friendly_type])
        human_type = GraphQLObjectType('Human', lambda: {
            'bestFriend': GraphQLField(friendly_type)}, interfaces=[
            friendly_type])
        schema = GraphQLSchema(
            GraphQLObjectType('WithInterface', {
                'friendly': GraphQLField(friendly_type)}),
            types=[dog_type, human_type])

        check_schema(schema)

    def builds_a_schema_with_an_implicit_interface():
        friendly_type = GraphQLInterfaceType('Friendly', lambda: {
                'bestFriend': GraphQLField(
                    friendly_type,
                    description='The best friend of this friendly thing.')})
        dog_type = GraphQLObjectType('DogType', lambda: {
            'bestFriend': GraphQLField(dog_type)}, interfaces=[friendly_type])
        schema = GraphQLSchema(GraphQLObjectType('WithInterface', {
            'dog': GraphQLField(dog_type)}))

        check_schema(schema)

    def builds_a_schema_with_a_union():
        dog_type = GraphQLObjectType(
            'Dog', lambda: {'bestFriend': GraphQLField(friendly_type)})
        human_type = GraphQLObjectType(
            'Human', lambda: {'bestFriend': GraphQLField(friendly_type)})
        friendly_type = GraphQLUnionType(
            'Friendly', types=[dog_type, human_type])
        schema = GraphQLSchema(GraphQLObjectType('WithUnion', {
            'friendly': GraphQLField(friendly_type)}))

        check_schema(schema)

    def builds_a_schema_with_complex_field_values():
        schema = GraphQLSchema(GraphQLObjectType('ComplexFields', {
            'string': GraphQLField(GraphQLString),
            'listOfString': GraphQLField(GraphQLList(GraphQLString)),
            'nonNullString': GraphQLField(GraphQLNonNull(GraphQLString)),
            'nonNullListOfString': GraphQLField(
                GraphQLNonNull(GraphQLList(GraphQLString))),
            'nonNullListOfNonNullString': GraphQLField(
                GraphQLNonNull(GraphQLList(GraphQLNonNull(GraphQLString))))}))

        check_schema(schema)

    def builds_a_schema_with_field_arguments():
        schema = GraphQLSchema(GraphQLObjectType('ArgFields', {
            'one': GraphQLField(
                GraphQLString, description='A field with a single arg', args={
                    'intArg': GraphQLArgument(
                        GraphQLInt, description='This is an int arg')}),
            'two': GraphQLField(
                GraphQLString, description='A field with two args', args={
                    'listArg': GraphQLArgument(
                        GraphQLList(GraphQLInt),
                        description='This is a list of int arg'),
                    'requiredArg': GraphQLArgument(
                            GraphQLNonNull(GraphQLBoolean),
                            description='This is a required arg')})}))

        check_schema(schema)

    def builds_a_schema_with_default_value_on_custom_scalar_field():
        schema = GraphQLSchema(GraphQLObjectType('ArgFields', {
            'testField': GraphQLField(GraphQLString, args={
                'testArg': GraphQLArgument(GraphQLScalarType(
                    'CustomScalar', serialize=lambda value: value),
                    default_value='default')})}))

        check_schema(schema)

    def builds_a_schema_with_an_enum():
        food_enum = GraphQLEnumType('Food', {
            'VEGETABLES': GraphQLEnumValue(
                1, description='Foods that are vegetables.'),
            'FRUITS': GraphQLEnumValue(
                2, description='Foods that are fruits.'),
            'OILS': GraphQLEnumValue(
                3, description='Foods that are oils.'),
            'DAIRY': GraphQLEnumValue(
                4, description='Foods that are dairy.'),
            'MEAT': GraphQLEnumValue(
                5, description='Foods that are meat.')},
            description='Varieties of food stuffs')

        schema = GraphQLSchema(GraphQLObjectType('EnumFields', {
            'food': GraphQLField(food_enum, args={
                'kind': GraphQLArgument(
                    food_enum, description='what kind of food?')},
                description='Repeats the arg you give it')}))

        check_schema(schema)

        introspection = introspection_from_schema(schema)
        client_schema = build_client_schema(introspection)
        client_food_enum = client_schema.get_type('Food')

        # It's also an Enum type on the client.
        assert isinstance(client_food_enum, GraphQLEnumType)

        values = client_food_enum.values
        descriptions = {
            name: value.description for name, value in values.items()}
        assert descriptions == {
            'VEGETABLES': 'Foods that are vegetables.',
            'FRUITS': 'Foods that are fruits.',
            'OILS': 'Foods that are oils.',
            'DAIRY': 'Foods that are dairy.',
            'MEAT': 'Foods that are meat.'}
        values = values.values()
        assert all(value.value is None for value in values)
        assert all(value.is_deprecated is False for value in values)
        assert all(value.deprecation_reason is None for value in values)
        assert all(value.ast_node is None for value in values)

    def builds_a_schema_with_an_input_object():
        address_type = GraphQLInputObjectType('Address', {
            'street': GraphQLInputField(
                GraphQLNonNull(GraphQLString),
                description='What street is this address?'),
            'city': GraphQLInputField(
                GraphQLNonNull(GraphQLString),
                description='The city the address is within?'),
            'country': GraphQLInputField(
                GraphQLString, default_value='USA',
                description='The country (blank will assume USA).')},
            description='An input address')

        schema = GraphQLSchema(GraphQLObjectType('HasInputObjectFields', {
            'geocode': GraphQLField(GraphQLString, args={
                'address': GraphQLArgument(
                    address_type, description='The address to lookup')},
                description='Get a geocode from an address')}))

        check_schema(schema)

    def builds_a_schema_with_field_arguments_with_default_values():
        geo_type = GraphQLInputObjectType('Geo', {
            'lat': GraphQLInputField(GraphQLFloat),
            'lon': GraphQLInputField(GraphQLFloat)})

        schema = GraphQLSchema(GraphQLObjectType('ArgFields', {
            'defaultInt': GraphQLField(GraphQLString, args={
                'intArg': GraphQLArgument(GraphQLInt, default_value=10)}),
            'defaultList': GraphQLField(GraphQLString, args={
                'listArg': GraphQLArgument(
                    GraphQLList(GraphQLInt), default_value=[1, 2, 3])}),
            'defaultObject': GraphQLField(GraphQLString, args={
                'objArg': GraphQLArgument(
                    geo_type,
                    default_value={'lat': 37.485, 'lon': -122.148})}),
            'defaultNull': GraphQLField(GraphQLString, args={
                'intArg': GraphQLArgument(GraphQLInt, default_value=None)}),
            'noDefaults': GraphQLField(GraphQLString, args={
                'intArg': GraphQLArgument(GraphQLInt)})}))

        check_schema(schema)

    def builds_a_schema_with_custom_directives():
        schema = GraphQLSchema(
            GraphQLObjectType('Simple', {
                'string': GraphQLField(
                    GraphQLString, description='This is a string field')},
                description='This is a simple type'),
            directives=[GraphQLDirective(
                'customDirective', [DirectiveLocation.FIELD],
                description='This is a custom directive')])

        check_schema(schema)

    def builds_a_schema_aware_of_deprecation():
        schema = GraphQLSchema(GraphQLObjectType('Simple', {
            'shinyString': GraphQLField(
                GraphQLString, description='This is a shiny string field'),
            'deprecatedString': GraphQLField(
                GraphQLString, description='This is a deprecated string field',
                deprecation_reason='Use shinyString'),
            'color': GraphQLField(
                GraphQLEnumType('Color', {
                    'RED': GraphQLEnumValue(description='So rosy'),
                    'GREEN': GraphQLEnumValue(description='So grassy'),
                    'BLUE': GraphQLEnumValue(description='So calming'),
                    'MAUVE': GraphQLEnumValue(
                        description='So sickening',
                        deprecation_reason='No longer in fashion')}))},
            description='This is a simple type'))

        check_schema(schema)

    def can_use_client_schema_for_limited_execution():
        custom_scalar = GraphQLScalarType(
            'CustomScalar', serialize=lambda: None)

        schema = GraphQLSchema(GraphQLObjectType('Query', {
            'foo': GraphQLField(GraphQLString, args={
                'custom1': GraphQLArgument(custom_scalar),
                'custom2': GraphQLArgument(custom_scalar)})}))

        introspection = introspection_from_schema(schema)
        client_schema = build_client_schema(introspection)

        class Data:
            foo = 'bar'
            unused = 'value'

        result = graphql_sync(
            client_schema,
            'query Limited($v: CustomScalar) {'
            ' foo(custom1: 123, custom2: $v) }',
            Data(), variable_values={'v': 'baz'})

        assert result.data == {'foo': 'bar'}


def describe_throws_when_given_incomplete_introspection():

    def throws_when_given_empty_types():
        incomplete_introspection = {
            '__schema': {
                'queryType': {'name': 'QueryType'},
                'types': []
            }
        }

        with raises(TypeError) as exc_info:
            build_client_schema(incomplete_introspection)

        assert str(exc_info.value) == (
            'Invalid or incomplete schema, unknown type: QueryType.'
            ' Ensure that a full introspection query is used'
            ' in order to build a client schema.')

    def throws_when_missing_kind():
        incomplete_introspection = {
            '__schema': {
                'queryType': {'name': 'QueryType'},
                'types': [{
                    'name': 'QueryType'
                }]
            }
        }

        with raises(TypeError) as exc_info:
            build_client_schema(incomplete_introspection)

        assert str(exc_info.value) == (
            'Invalid or incomplete introspection result.'
            ' Ensure that a full introspection query is used'
            " in order to build a client schema: {'name': 'QueryType'}")

    def throws_when_missing_interfaces():
        null_interface_introspection = {
            '__schema': {
                'queryType': {'name': 'QueryType'},
                'types': [{
                    'kind': 'OBJECT',
                    'name': 'QueryType',
                    'fields': [{
                        'name': 'aString',
                        'args': [],
                        'type': {
                            'kind': 'SCALAR', 'name': 'String',
                            'ofType': None},
                        'isDeprecated': False
                        }]
                }]
            }
        }

        with raises(TypeError) as exc_info:
            build_client_schema(null_interface_introspection)

        assert str(exc_info.value) == (
            'Introspection result missing interfaces:'
            " {'kind': 'OBJECT', 'name': 'QueryType',"
            " 'fields': [{'name': 'aString', 'args': [],"
            " 'type': {'kind': 'SCALAR', 'name': 'String', 'ofType': None},"
            " 'isDeprecated': False}]}")


def describe_very_deep_decorators_are_not_supported():

    def fails_on_very_deep_lists_more_than_7_levels():
        schema = GraphQLSchema(GraphQLObjectType('Query', {
            'foo': GraphQLField(
                GraphQLList(GraphQLList(GraphQLList(GraphQLList(
                    GraphQLList(GraphQLList(GraphQLList(GraphQLList(
                        GraphQLString)))))))))}))

        introspection = introspection_from_schema(schema)

        with raises(TypeError) as exc_info:
            build_client_schema(introspection)

        assert str(exc_info.value) == (
            'Query fields cannot be resolved:'
            ' Decorated type deeper than introspection query.')

    def fails_on_a_very_deep_non_null_more_than_7_levels():
        schema = GraphQLSchema(GraphQLObjectType('Query', {
            'foo': GraphQLField(
                GraphQLList(GraphQLNonNull(GraphQLList(GraphQLNonNull(
                    GraphQLList(GraphQLNonNull(GraphQLList(GraphQLNonNull(
                        GraphQLString)))))))))}))

        introspection = introspection_from_schema(schema)

        with raises(TypeError) as exc_info:
            build_client_schema(introspection)

        assert str(exc_info.value) == (
            'Query fields cannot be resolved:'
            ' Decorated type deeper than introspection query.')

    def succeeds_on_deep_types_less_or_equal_7_levels():
        schema = GraphQLSchema(GraphQLObjectType('Query', {
            'foo': GraphQLField(
                # e.g., fully non-null 3D matrix
                GraphQLNonNull(GraphQLList(GraphQLNonNull(GraphQLList(
                    GraphQLNonNull(GraphQLList(GraphQLNonNull(
                        GraphQLString))))))))}))

        introspection = introspection_from_schema(schema)
        build_client_schema(introspection)
