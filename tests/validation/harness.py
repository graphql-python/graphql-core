from typing import List, Optional, Type

from graphql.error import GraphQLError
from graphql.language import parse
from graphql.type import (
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLFloat,
    GraphQLID,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
    GraphQLUnionType,
    GraphQLScalarType,
)
from graphql.type.directives import (
    DirectiveLocation,
    GraphQLDirective,
    GraphQLIncludeDirective,
    GraphQLSkipDirective,
)
from graphql.validation import ValidationRule, SDLValidationRule
from graphql.validation.validate import validate, validate_sdl

Being = GraphQLInterfaceType(
    "Being",
    {"name": GraphQLField(GraphQLString, {"surname": GraphQLArgument(GraphQLBoolean)})},
)

Mammal = GraphQLInterfaceType(
    "Mammal",
    lambda: {
        "mother": GraphQLField(Mammal),  # type: ignore
        "father": GraphQLField(Mammal),  # type: ignore
    },
    interfaces=[],
)

Pet = GraphQLInterfaceType(
    "Pet",
    {"name": GraphQLField(GraphQLString, {"surname": GraphQLArgument(GraphQLBoolean)})},
    interfaces=[Being],
)

Canine = GraphQLInterfaceType(
    "Canine",
    lambda: {
        "name": GraphQLField(
            GraphQLString, {"surname": GraphQLArgument(GraphQLBoolean)}
        ),
        "mother": GraphQLField(Canine),  # type: ignore
        "father": GraphQLField(Canine),  # type: ignore
    },
    interfaces=[Mammal, Being],
)

DogCommand = GraphQLEnumType(
    "DogCommand",
    {
        "SIT": GraphQLEnumValue(0),
        "HEEL": GraphQLEnumValue(1),
        "DOWN": GraphQLEnumValue(2),
    },
)

Dog = GraphQLObjectType(
    "Dog",
    lambda: {
        "name": GraphQLField(
            GraphQLString, {"surname": GraphQLArgument(GraphQLBoolean)}
        ),
        "nickname": GraphQLField(GraphQLString),
        "barkVolume": GraphQLField(GraphQLInt),
        "barks": GraphQLField(GraphQLBoolean),
        "doesKnowCommand": GraphQLField(
            GraphQLBoolean, {"dogCommand": GraphQLArgument(DogCommand)}
        ),
        "isHouseTrained": GraphQLField(
            GraphQLBoolean,
            args={"atOtherHomes": GraphQLArgument(GraphQLBoolean, default_value=True)},
        ),
        "isAtLocation": GraphQLField(
            GraphQLBoolean,
            args={"x": GraphQLArgument(GraphQLInt), "y": GraphQLArgument(GraphQLInt)},
        ),
        "mother": GraphQLField(Dog),  # type: ignore
        "father": GraphQLField(Dog),  # type: ignore
    },
    interfaces=[Being, Pet, Mammal, Canine],
)

FurColor: GraphQLEnumType

Cat = GraphQLObjectType(
    "Cat",
    lambda: {
        "furColor": GraphQLField(FurColor),
        "name": GraphQLField(
            GraphQLString, {"surname": GraphQLArgument(GraphQLBoolean)}
        ),
        "nickname": GraphQLField(GraphQLString),
    },
    interfaces=[Being, Pet],
)

CatOrDog = GraphQLUnionType("CatOrDog", [Dog, Cat])

Intelligent = GraphQLInterfaceType("Intelligent", {"iq": GraphQLField(GraphQLInt)})

Human = GraphQLObjectType(
    name="Human",
    interfaces=[Being, Intelligent],
    fields={
        "name": GraphQLField(
            GraphQLString, {"surname": GraphQLArgument(GraphQLBoolean)}
        ),
        "pets": GraphQLField(GraphQLList(Pet)),
        "iq": GraphQLField(GraphQLInt),
    },
)

Alien = GraphQLObjectType(
    name="Alien",
    interfaces=[Being, Intelligent],
    fields={
        "iq": GraphQLField(GraphQLInt),
        "name": GraphQLField(
            GraphQLString, {"surname": GraphQLArgument(GraphQLBoolean)}
        ),
        "numEyes": GraphQLField(GraphQLInt),
    },
)

DogOrHuman = GraphQLUnionType("DogOrHuman", [Dog, Human])

HumanOrAlien = GraphQLUnionType("HumanOrAlien", [Human, Alien])

FurColor = GraphQLEnumType(
    "FurColor",
    {
        "BROWN": GraphQLEnumValue(0),
        "BLACK": GraphQLEnumValue(1),
        "TAN": GraphQLEnumValue(2),
        "SPOTTED": GraphQLEnumValue(3),
        "NO_FUR": GraphQLEnumValue(),
        "UNKNOWN": None,
    },
)

ComplexInput = GraphQLInputObjectType(
    "ComplexInput",
    {
        "requiredField": GraphQLInputField(GraphQLNonNull(GraphQLBoolean)),
        "nonNullField": GraphQLInputField(
            GraphQLNonNull(GraphQLBoolean), default_value=False
        ),
        "intField": GraphQLInputField(GraphQLInt),
        "stringField": GraphQLInputField(GraphQLString),
        "booleanField": GraphQLInputField(GraphQLBoolean),
        "stringListField": GraphQLInputField(GraphQLList(GraphQLString)),
    },
)

ComplicatedArgs = GraphQLObjectType(
    "ComplicatedArgs",
    {
        "intArgField": GraphQLField(
            GraphQLString, {"intArg": GraphQLArgument(GraphQLInt)}
        ),
        "nonNullIntArgField": GraphQLField(
            GraphQLString,
            {"nonNullIntArg": GraphQLArgument(GraphQLNonNull(GraphQLInt))},
        ),
        "stringArgField": GraphQLField(
            GraphQLString, {"stringArg": GraphQLArgument(GraphQLString)}
        ),
        "booleanArgField": GraphQLField(
            GraphQLString, {"booleanArg": GraphQLArgument(GraphQLBoolean)}
        ),
        "enumArgField": GraphQLField(
            GraphQLString, {"enumArg": GraphQLArgument(FurColor)}
        ),
        "floatArgField": GraphQLField(
            GraphQLString, {"floatArg": GraphQLArgument(GraphQLFloat)}
        ),
        "idArgField": GraphQLField(
            GraphQLString, {"idArg": GraphQLArgument(GraphQLID)}
        ),
        "stringListArgField": GraphQLField(
            GraphQLString,
            {"stringListArg": GraphQLArgument(GraphQLList(GraphQLString))},
        ),
        "stringListNonNullArgField": GraphQLField(
            GraphQLString,
            args={
                "stringListNonNullArg": GraphQLArgument(
                    GraphQLList(GraphQLNonNull(GraphQLString))
                )
            },
        ),
        "complexArgField": GraphQLField(
            GraphQLString, {"complexArg": GraphQLArgument(ComplexInput)}
        ),
        "multipleReqs": GraphQLField(
            GraphQLString,
            {
                "req1": GraphQLArgument(GraphQLNonNull(GraphQLInt)),
                "req2": GraphQLArgument(GraphQLNonNull(GraphQLInt)),
            },
        ),
        "nonNullFieldWithDefault": GraphQLField(
            GraphQLString,
            {"arg": GraphQLArgument(GraphQLNonNull(GraphQLInt), default_value=0)},
        ),
        "multipleOpts": GraphQLField(
            GraphQLString,
            {
                "opt1": GraphQLArgument(GraphQLInt, 0),
                "opt2": GraphQLArgument(GraphQLInt, 0),
            },
        ),
        "multipleOptsAndReq": GraphQLField(
            GraphQLString,
            {
                "req1": GraphQLArgument(GraphQLNonNull(GraphQLInt)),
                "req2": GraphQLArgument(GraphQLNonNull(GraphQLInt)),
                "opt1": GraphQLArgument(GraphQLInt, 0),
                "opt2": GraphQLArgument(GraphQLInt, 0),
            },
        ),
    },
)


def raise_type_error(message):
    raise TypeError(message)


InvalidScalar = GraphQLScalarType(
    name="Invalid",
    parse_value=lambda value: raise_type_error(
        f"Invalid scalar is always invalid: {value!r}"
    ),
)

AnyScalar = GraphQLScalarType(name="Any")

QueryRoot = GraphQLObjectType(
    "QueryRoot",
    {
        "human": GraphQLField(Human, {"id": GraphQLArgument(GraphQLID)}),
        "dog": GraphQLField(Dog),
        "pet": GraphQLField(Pet),
        "alien": GraphQLField(Alien),
        "catOrDog": GraphQLField(CatOrDog),
        "humanOrAlien": GraphQLField(HumanOrAlien),
        "complicatedArgs": GraphQLField(ComplicatedArgs),
        "invalidArg": GraphQLField(
            GraphQLString, args={"arg": GraphQLArgument(InvalidScalar)}
        ),
        "anyArg": GraphQLField(GraphQLString, args={"arg": GraphQLArgument(AnyScalar)}),
    },
)

test_schema = GraphQLSchema(
    query=QueryRoot,
    directives=[
        GraphQLIncludeDirective,
        GraphQLSkipDirective,
        GraphQLDirective(name="onQuery", locations=[DirectiveLocation.QUERY]),
        GraphQLDirective(name="onMutation", locations=[DirectiveLocation.MUTATION]),
        GraphQLDirective(
            name="onSubscription", locations=[DirectiveLocation.SUBSCRIPTION]
        ),
        GraphQLDirective(name="onField", locations=[DirectiveLocation.FIELD]),
        GraphQLDirective(
            name="onFragmentDefinition",
            locations=[DirectiveLocation.FRAGMENT_DEFINITION],
        ),
        GraphQLDirective(
            name="onFragmentSpread", locations=[DirectiveLocation.FRAGMENT_SPREAD]
        ),
        GraphQLDirective(
            name="onInlineFragment", locations=[DirectiveLocation.INLINE_FRAGMENT]
        ),
        GraphQLDirective(
            name="onVariableDefinition",
            locations=[DirectiveLocation.VARIABLE_DEFINITION],
        ),
    ],
    types=[Cat, Dog, Human, Alien],
)


def assert_validation_errors(
    rule: Type[ValidationRule],
    query_str: str,
    errors: List[GraphQLError],
    schema: GraphQLSchema = test_schema,
) -> List[GraphQLError]:
    doc = parse(query_str)
    returned_errors = validate(schema, doc, [rule])
    assert returned_errors == errors
    return returned_errors


def assert_sdl_validation_errors(
    rule: Type[SDLValidationRule],
    sdl_str: str,
    errors: List[GraphQLError],
    schema: Optional[GraphQLSchema] = None,
) -> List[GraphQLError]:
    doc = parse(sdl_str)
    returned_errors = validate_sdl(doc, schema, [rule])
    assert returned_errors == errors
    return returned_errors
