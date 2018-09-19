from graphql.pyutils import camel_to_snake, snake_to_camel


def describe_camel_to_snake():
    def converts_typical_names():
        result = camel_to_snake("CamelCase")
        assert result == "camel_case"
        result = camel_to_snake("InputObjectTypeExtensionNode")
        assert result == "input_object_type_extension_node"

    def may_start_with_lowercase():
        result = camel_to_snake("CamelCase")
        assert result == "camel_case"

    def works_with_acronyms():
        result = camel_to_snake("SlowXMLParser")
        assert result == "slow_xml_parser"
        result = camel_to_snake("FastGraphQLParser")
        assert result == "fast_graph_ql_parser"

    def keeps_already_snake():
        result = camel_to_snake("snake_case")
        assert result == "snake_case"


def describe_snake_to_camel():
    def converts_typical_names():
        result = snake_to_camel("snake_case")
        assert result == "SnakeCase"
        result = snake_to_camel("input_object_type_extension_node")
        assert result == "InputObjectTypeExtensionNode"

    def may_start_with_uppercase():
        result = snake_to_camel("Snake_case")
        assert result == "SnakeCase"

    def works_with_acronyms():
        result = snake_to_camel("slow_xml_parser")
        assert result == "SlowXmlParser"
        result = snake_to_camel("fast_graph_ql_parser")
        assert result == "FastGraphQlParser"

    def keeps_already_camel():
        result = snake_to_camel("CamelCase")
        assert result == "CamelCase"

    def can_produce_lower_camel_case():
        result = snake_to_camel("snake_case", upper=False)
        assert result == "snakeCase"
        result = snake_to_camel("input_object_type_extension_node", False)
        assert result == "inputObjectTypeExtensionNode"
