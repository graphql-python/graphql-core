from typing import List, Optional, Type

from graphql.error import GraphQLError
from graphql.language import parse
from graphql.type import GraphQLSchema
from graphql.utilities import build_schema
from graphql.validation import ValidationRule, SDLValidationRule
from graphql.validation.validate import validate, validate_sdl

__all__ = [
    "test_schema",
    "assert_validation_errors",
    "assert_sdl_validation_errors",
]

test_schema = build_schema(
    """
   interface Mammal {
      mother: Mammal
      father: Mammal
    }

    interface Pet {
      name(surname: Boolean): String
    }

    interface Canine implements Mammal {
      name(surname: Boolean): String
      mother: Canine
      father: Canine
    }

    enum DogCommand {
      SIT
      HEEL
      DOWN
    }

    type Dog implements Pet & Mammal & Canine {
      name(surname: Boolean): String
      nickname: String
      barkVolume: Int
      barks: Boolean
      doesKnowCommand(dogCommand: DogCommand): Boolean
      isHouseTrained(atOtherHomes: Boolean = true): Boolean
      isAtLocation(x: Int, y: Int): Boolean
      mother: Dog
      father: Dog
    }

    type Cat implements Pet {
      name(surname: Boolean): String
      nickname: String
      meows: Boolean
      meowsVolume: Int
      furColor: FurColor
    }

    union CatOrDog = Cat | Dog

    type Human {
      name(surname: Boolean): String
      pets: [Pet]
      relatives: [Human]
    }

    enum FurColor {
      BROWN
      BLACK
      TAN
      SPOTTED
      NO_FUR
      UNKNOWN
    }

    input ComplexInput {
      requiredField: Boolean!
      nonNullField: Boolean! = false
      intField: Int
      stringField: String
      booleanField: Boolean
      stringListField: [String]
    }

    type ComplicatedArgs {
      # TODO List
      # TODO Coercion
      # TODO NotNulls
      intArgField(intArg: Int): String
      nonNullIntArgField(nonNullIntArg: Int!): String
      stringArgField(stringArg: String): String
      booleanArgField(booleanArg: Boolean): String
      enumArgField(enumArg: FurColor): String
      floatArgField(floatArg: Float): String
      idArgField(idArg: ID): String
      stringListArgField(stringListArg: [String]): String
      stringListNonNullArgField(stringListNonNullArg: [String!]): String
      complexArgField(complexArg: ComplexInput): String
      multipleReqs(req1: Int!, req2: Int!): String
      nonNullFieldWithDefault(arg: Int! = 0): String
      multipleOpts(opt1: Int = 0, opt2: Int = 0): String
      multipleOptAndReq(req1: Int!, req2: Int!, opt1: Int = 0, opt2: Int = 0): String
    }

    type QueryRoot {
      human(id: ID): Human
      dog: Dog
      cat: Cat
      pet: Pet
      catOrDog: CatOrDog
      complicatedArgs: ComplicatedArgs
    }

    schema {
      query: QueryRoot
    }

    directive @onField on FIELD
    """
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
