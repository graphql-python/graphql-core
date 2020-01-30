"""This defines a basic set of data for our Star Wars Schema.

This data is hard coded for the sake of the demo, but you could imagine fetching this
data from a backend service rather than from hardcoded JSON objects in a more complex
demo.
"""

from typing import Awaitable, Collection, Iterator

__all__ = ["get_droid", "get_friends", "get_hero", "get_human", "get_secret_backstory"]

# These are classes which correspond to the schema.
# They represent the shape of the data visited during field resolution.


class Character:
    id: str
    name: str
    friends: Collection[str]
    appearsIn: Collection[str]


# noinspection PyPep8Naming
class Human(Character):
    type = "Human"
    homePlanet: str

    # noinspection PyShadowingBuiltins
    def __init__(self, id, name, friends, appearsIn, homePlanet):
        self.id, self.name = id, name
        self.friends, self.appearsIn = friends, appearsIn
        self.homePlanet = homePlanet


# noinspection PyPep8Naming
class Droid(Character):
    type = "Droid"
    primaryFunction: str

    # noinspection PyShadowingBuiltins
    def __init__(self, id, name, friends, appearsIn, primaryFunction):
        self.id, self.name = id, name
        self.friends, self.appearsIn = friends, appearsIn
        self.primaryFunction = primaryFunction


luke = Human(
    id="1000",
    name="Luke Skywalker",
    friends=["1002", "1003", "2000", "2001"],
    appearsIn=[4, 5, 6],
    homePlanet="Tatooine",
)

vader = Human(
    id="1001",
    name="Darth Vader",
    friends=["1004"],
    appearsIn=[4, 5, 6],
    homePlanet="Tatooine",
)

han = Human(
    id="1002",
    name="Han Solo",
    friends=["1000", "1003", "2001"],
    appearsIn=[4, 5, 6],
    homePlanet=None,
)

leia = Human(
    id="1003",
    name="Leia Organa",
    friends=["1000", "1002", "2000", "2001"],
    appearsIn=[4, 5, 6],
    homePlanet="Alderaan",
)

tarkin = Human(
    id="1004", name="Wilhuff Tarkin", friends=["1001"], appearsIn=[4], homePlanet=None
)

human_data = {"1000": luke, "1001": vader, "1002": han, "1003": leia, "1004": tarkin}

threepio = Droid(
    id="2000",
    name="C-3PO",
    friends=["1000", "1002", "1003", "2001"],
    appearsIn=[4, 5, 6],
    primaryFunction="Protocol",
)

artoo = Droid(
    id="2001",
    name="R2-D2",
    friends=["1000", "1002", "1003"],
    appearsIn=[4, 5, 6],
    primaryFunction="Astromech",
)

droid_data = {"2000": threepio, "2001": artoo}


# noinspection PyShadowingBuiltins
async def get_character(id: str) -> Character:
    """Helper function to get a character by ID."""
    # We use an async function just to illustrate that GraphQL-core supports it.
    return human_data.get(id) or droid_data.get(id)  # type: ignore


def get_friends(character: Character) -> Iterator[Awaitable[Character]]:
    """Allows us to query for a character's friends."""
    # Notice that GraphQL-core accepts iterators of awaitables.
    return map(get_character, character.friends)


def get_hero(episode: int) -> Character:
    """Allows us to fetch the undisputed hero of the trilogy, R2-D2."""
    if episode == 5:
        # Luke is the hero of Episode V.
        return luke
    # Artoo is the hero otherwise.
    return artoo


# noinspection PyShadowingBuiltins
def get_human(id: str) -> Human:
    """Allows us to query for the human with the given id."""
    return human_data.get(id)  # type: ignore


# noinspection PyShadowingBuiltins
def get_droid(id: str) -> Droid:
    """Allows us to query for the droid with the given id."""
    return droid_data.get(id)  # type: ignore


# noinspection PyUnusedLocal
def get_secret_backstory(character: Character) -> str:
    """Raise an error when attempting to get the secret backstory."""
    raise RuntimeError("secretBackstory is secret.")
