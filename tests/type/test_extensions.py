from pytest import param

from graphql.type import (
    GraphQLArgument,
    GraphQLDirective,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLUnionType,
)


dummy_type = GraphQLScalarType("DummyScalar")

bad_extensions = [param([], id="list"), param({1: "ext"}, id="non_string_key")]


def describe_type_system_extensions():
    def describe_graphql_scalar_type():
        def without_extensions():
            some_scalar = GraphQLScalarType("SomeScalar")
            assert some_scalar.extensions == {}
            assert some_scalar.to_kwargs()["extensions"] == {}

        def with_extensions():
            scalar_extensions = {"SomeScalarExt": "scalar"}
            some_scalar = GraphQLScalarType("SomeScalar", extensions=scalar_extensions)

            assert some_scalar.extensions is scalar_extensions
            assert some_scalar.to_kwargs()["extensions"] is scalar_extensions

    def describe_graphql_object_type():
        def without_extensions():
            some_object = GraphQLObjectType(
                "SomeObject",
                {
                    "someField": GraphQLField(
                        dummy_type, {"someArg": GraphQLArgument(dummy_type)}
                    )
                },
            )

            assert some_object.extensions == {}
            some_field = some_object.fields["someField"]
            assert some_field.extensions == {}
            some_arg = some_field.args["someArg"]
            assert some_arg.extensions == {}

            assert some_object.to_kwargs()["extensions"] == {}
            assert some_field.to_kwargs()["extensions"] == {}
            assert some_arg.to_kwargs()["extensions"] == {}

        def with_extensions():
            object_extensions = {"SomeObjectExt": "object"}
            field_extensions = {"SomeFieldExt": "field"}
            arg_extensions = {"SomeArgExt": "arg"}

            some_object = GraphQLObjectType(
                "SomeObject",
                {
                    "someField": GraphQLField(
                        dummy_type,
                        {
                            "someArg": GraphQLArgument(
                                dummy_type, extensions=arg_extensions
                            )
                        },
                        extensions=field_extensions,
                    )
                },
                extensions=object_extensions,
            )

            assert some_object.extensions is object_extensions
            some_field = some_object.fields["someField"]
            assert some_field.extensions is field_extensions
            some_arg = some_field.args["someArg"]
            assert some_arg.extensions is arg_extensions

            assert some_object.to_kwargs()["extensions"] is object_extensions
            assert some_field.to_kwargs()["extensions"] is field_extensions
            assert some_arg.to_kwargs()["extensions"] is arg_extensions

    def describe_graphql_interface_type():
        def without_extensions():
            some_interface = GraphQLInterfaceType(
                "SomeInterface",
                {
                    "someField": GraphQLField(
                        dummy_type, {"someArg": GraphQLArgument(dummy_type)}
                    )
                },
            )

            assert some_interface.extensions == {}
            some_field = some_interface.fields["someField"]
            assert some_field.extensions == {}
            some_arg = some_field.args["someArg"]
            assert some_arg.extensions == {}

            assert some_interface.to_kwargs()["extensions"] == {}
            assert some_field.to_kwargs()["extensions"] == {}
            assert some_arg.to_kwargs()["extensions"] == {}

        def with_extensions():
            interface_extensions = {"SomeInterfaceExt": "interface"}
            field_extensions = {"SomeFieldExt": "field"}
            arg_extensions = {"SomeArgExt": "arg"}

            some_interface = GraphQLInterfaceType(
                "SomeInterface",
                {
                    "someField": GraphQLField(
                        dummy_type,
                        {
                            "someArg": GraphQLArgument(
                                dummy_type, extensions=arg_extensions
                            )
                        },
                        extensions=field_extensions,
                    )
                },
                extensions=interface_extensions,
            )

            assert some_interface.extensions is interface_extensions
            some_field = some_interface.fields["someField"]
            assert some_field.extensions is field_extensions
            some_arg = some_field.args["someArg"]
            assert some_arg.extensions is arg_extensions

            assert some_interface.to_kwargs()["extensions"] is interface_extensions
            assert some_field.to_kwargs()["extensions"] is field_extensions
            assert some_arg.to_kwargs()["extensions"] is arg_extensions

    def describe_graphql_union_type():
        def without_extensions():
            some_union = GraphQLUnionType("SomeUnion", [])

            assert some_union.extensions == {}

            assert some_union.to_kwargs()["extensions"] == {}

        def with_extensions():
            union_extensions = {"SomeUnionExt": "union"}

            some_union = GraphQLUnionType("SomeUnion", [], extensions=union_extensions)

            assert some_union.extensions is union_extensions

            assert some_union.to_kwargs()["extensions"] is union_extensions

    def describe_graphql_enum_type():
        def without_extensions():
            some_enum = GraphQLEnumType("SomeEnum", {"SOME_VALUE": None})

            assert some_enum.extensions == {}
            some_value = some_enum.values["SOME_VALUE"]
            assert some_value.extensions == {}

            assert some_enum.to_kwargs()["extensions"] == {}
            assert some_value.to_kwargs()["extensions"] == {}

        def with_extensions():
            enum_extensions = {"SomeEnumExt": "enum"}
            value_extensions = {"SomeValueExt": "value"}

            some_enum = GraphQLEnumType(
                "SomeEnum",
                {"SOME_VALUE": GraphQLEnumValue(extensions=value_extensions)},
                extensions=enum_extensions,
            )

            assert some_enum.extensions is enum_extensions
            some_value = some_enum.values["SOME_VALUE"]
            assert some_value.extensions is value_extensions

            assert some_enum.to_kwargs()["extensions"] is enum_extensions
            assert some_value.to_kwargs()["extensions"] is value_extensions

    def describe_graphql_input_object_type():
        def without_extensions():
            some_input_object = GraphQLInputObjectType(
                "SomeInputObject", {"someInputField": GraphQLInputField(dummy_type)}
            )

            assert some_input_object.extensions == {}
            some_input_field = some_input_object.fields["someInputField"]
            assert some_input_field.extensions == {}

            assert some_input_object.to_kwargs()["extensions"] == {}
            assert some_input_field.to_kwargs()["extensions"] == {}

        def with_extensions():
            input_object_extensions = {"SomeInputObjectExt": "inputObject"}
            input_field_extensions = {"SomeInputFieldExt": "inputField"}

            some_input_object = GraphQLInputObjectType(
                "SomeInputObject",
                {
                    "someInputField": GraphQLInputField(
                        dummy_type, extensions=input_field_extensions
                    )
                },
                extensions=input_object_extensions,
            )

            assert some_input_object.extensions is input_object_extensions
            some_input_field = some_input_object.fields["someInputField"]
            assert some_input_field.extensions is input_field_extensions

            assert (
                some_input_object.to_kwargs()["extensions"] is input_object_extensions
            )
            assert some_input_field.to_kwargs()["extensions"] is input_field_extensions

    def describe_graphql_directive():
        def without_extensions():
            some_directive = GraphQLDirective(
                "SomeDirective", [], {"someArg": GraphQLArgument(dummy_type)}
            )

            assert some_directive.extensions == {}
            some_arg = some_directive.args["someArg"]
            assert some_arg.extensions == {}

            assert some_directive.to_kwargs()["extensions"] == {}
            assert some_arg.to_kwargs()["extensions"] == {}

        def with_extensions():
            directive_extensions = {"SomeDirectiveExt": "directive"}
            arg_extensions = {"SomeArgExt": "arg"}

            some_directive = GraphQLDirective(
                "SomeDirective",
                [],
                {"someArg": GraphQLArgument(dummy_type, extensions=arg_extensions)},
                extensions=directive_extensions,
            )

            assert some_directive.extensions is directive_extensions
            some_arg = some_directive.args["someArg"]
            assert some_arg.extensions is arg_extensions

            assert some_directive.to_kwargs()["extensions"] is directive_extensions
            assert some_arg.to_kwargs()["extensions"] is arg_extensions

    def describe_graphql_schema():
        def without_extensions():
            schema = GraphQLSchema()

            assert schema.extensions == {}
            assert schema.to_kwargs()["extensions"] == {}

        def with_extensions():
            schema_extensions = {"schemaExtension": "schema"}

            schema = GraphQLSchema(extensions=schema_extensions)

            assert schema.extensions is schema_extensions

            assert schema.to_kwargs()["extensions"] is schema_extensions
