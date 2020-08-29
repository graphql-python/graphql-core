Implementing the Resolver Functions
-----------------------------------

.. currentmodule:: graphql.type

Before we can execute queries against our schema, we also need to define the data (the
humans and droids appearing in the Star Wars trilogy) and implement resolver functions
that fetch the data (at the beginning of our schema module, because we are referencing
them later)::

    luke = dict(
        id='1000', name='Luke Skywalker', homePlanet='Tatooine',
        friends=['1002', '1003', '2000', '2001'], appearsIn=[4, 5, 6])

    vader = dict(
        id='1001', name='Darth Vader', homePlanet='Tatooine',
        friends=['1004'], appearsIn=[4, 5, 6])

    han = dict(
        id='1002', name='Han Solo', homePlanet=None,
        friends=['1000', '1003', '2001'], appearsIn=[4, 5, 6])

    leia = dict(
        id='1003', name='Leia Organa', homePlanet='Alderaan',
        friends=['1000', '1002', '2000', '2001'], appearsIn=[4, 5, 6])

    tarkin = dict(
        id='1004', name='Wilhuff Tarkin', homePlanet=None,
        friends=['1001'], appearsIn=[4])

    human_data = {
        '1000': luke, '1001': vader, '1002': han, '1003': leia, '1004': tarkin}

    threepio = dict(
        id='2000', name='C-3PO', primaryFunction='Protocol',
        friends=['1000', '1002', '1003', '2001'], appearsIn=[4, 5, 6])

    artoo = dict(
        id='2001', name='R2-D2', primaryFunction='Astromech',
        friends=['1000', '1002', '1003'], appearsIn=[4, 5, 6])

    droid_data = {
        '2000': threepio, '2001': artoo}


    def get_character_type(character, _info, _type):
            return 'Droid' if character['id'] in droid_data else 'Human'


    def get_character(id):
        """Helper function to get a character by ID."""
        return human_data.get(id) or droid_data.get(id)


    def get_friends(character, _info):
        """Allows us to query for a character's friends."""
        return map(get_character, character.friends)


    def get_hero(root, _info, episode):
        """Allows us to fetch the undisputed hero of the trilogy, R2-D2."""
        if episode == 5:
            return luke  # Luke is the hero of Episode V
        return artoo  # Artoo is the hero otherwise


    def get_human(root, _info, id):
        """Allows us to query for the human with the given id."""
        return human_data.get(id)


    def get_droid(root, _info, id):
        """Allows us to query for the droid with the given id."""
        return droid_data.get(id)


    def get_secret_backstory(_character, _info):
        """Raise an error when attempting to get the secret backstory."""
        raise RuntimeError('secretBackstory is secret.')


Note that the resolver functions get the current object as first argument. For a field
on the root Query type this is often not used, but a root object can also be defined
when executing the query. As the second argument, they get an object containing
execution information, as defined in the :class:`~GraphQLResolveInfo` class.
This object also has a ``context`` attribute that can be used to provide every resolver
with contextual information like the currently logged in user, or a database session.
In our simple example we don't authenticate users and use static data instead of a
database, so we don't make use of it here. In addition to these two arguments,
resolver functions optionally get the defined for the field in the schema, using the
same names (the names are not translated from GraphQL naming conventions to Python
naming conventions).

Also note that you don't need to provide resolvers for simple attribute access or for
fetching items from Python dictionaries.

Finally, note that our data uses the internal values of the ``Episode`` enum that we
have defined above, not the descriptive enum names that are used externally. For
example, ``NEWHOPE`` ("A New Hope") has internally the actual episode number 4 as value.
