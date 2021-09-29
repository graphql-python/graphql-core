from graphql.pyutils import camel_to_snake, snake_to_camel


def describe_camel_to_snake():
    def converts_typical_names():
        assert camel_to_snake("CamelCase") == "camel_case"
        assert (
            camel_to_snake("InputObjectTypeExtensionNode")
            == "input_object_type_extension_node"
        )
        assert camel_to_snake("CamelToSnake") == "camel_to_snake"

    def may_start_with_lowercase():
        assert camel_to_snake("camelCase") == "camel_case"

    def works_with_acronyms():
        assert camel_to_snake("SlowXMLParser") == "slow_xml_parser"
        assert camel_to_snake("FastGraphQLParser") == "fast_graph_ql_parser"

    def works_with_numbers():
        assert camel_to_snake("Python3Script") == "python3_script"
        assert camel_to_snake("camel2snake") == "camel2snake"

    def keeps_already_snake():
        assert camel_to_snake("snake_case") == "snake_case"


def describe_snake_to_camel():
    def converts_typical_names():
        assert snake_to_camel("snake_case") == "SnakeCase"
        assert (
            snake_to_camel("input_object_type_extension_node")
            == "InputObjectTypeExtensionNode"
        )
        assert snake_to_camel("snake_to_camel") == "SnakeToCamel"

    def may_start_with_uppercase():
        assert snake_to_camel("Snake_case") == "SnakeCase"

    def works_with_acronyms():
        assert snake_to_camel("slow_xml_parser") == "SlowXmlParser"
        assert snake_to_camel("fast_graph_ql_parser") == "FastGraphQlParser"

    def works_with_numbers():
        assert snake_to_camel("python3_script") == "Python3Script"
        assert snake_to_camel("snake2camel") == "Snake2camel"

    def keeps_already_camel():
        assert snake_to_camel("CamelCase") == "CamelCase"

    def can_produce_lower_camel_case():
        assert snake_to_camel("snake_case", upper=False) == "snakeCase"
        assert (
            snake_to_camel("input_object_type_extension_node", False)
            == "inputObjectTypeExtensionNode"
        )
