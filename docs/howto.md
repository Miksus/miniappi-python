# Tutorials

This section covers how to create Miniappi
apps with Python.

## Basics

### Showing content

To display user some content:

```python
from miniappi import content

@app.on_open()
async def new_user(session):
    cont = content.v0.widgets.InputText()

    # Show the input box
    await cont.show()
```

Browse the available content types
[from the content section](content/index.md).

### Nesting content

Some fields of some content types can be nested,
ie. you can have cards inside a card:

```python
@app.on_open()
async def new_user(session):
    Card = content.v0.cards.Card
    cont = content.v0.layouts.Grid(
        cols=2,
        contents=[
            Card(title="First card"),
            Card(title="Second card"),
            Card(title="Third card"),
            Card(title="Forth card"),
        ]
    )

    await cont.show()
```

### Waiting for user input

Some content can be clicked, typed or
otherwise interacted with. To get the
user input, you can use ``wait_input``
method:

```python
@app.on_open()
async def new_user(session):
    cont = content.v0.widgets.InputText()

    # Waiting for user input
    text = await cont.wait_input()
    print(text)
    # {'id': '...', 'value': '<some text>'}
```

!!! warning "Not all content is interactive!"

    If the component or all of its children
    are not interactive, this will wait forever.

!!! tip

    If you don't want to trigger rendering,
    you can pass ``wait_input(show=False)``
    to just wait for input.

## Advanced

The remaining sections are advanced.
Please familiarize yourself with
other topics before going to these
topics.

### Show content from global state

To show all users the same content,
simply call the ``show`` method
in a function that runs in app
scope (ie. ``on_start``):

```python
@app.on_start()
async def start_app():
    ...

    # Wait for some users joining
    await asyncio.sleep(60)

    cont = content.v0.Title(
        text="Game starts!"
    )
    # Show to all users
    await cont.show()
```

Or you can fetch specific user's session
by iterating open sessions:

```python
from miniappi import app_context

@app.on_start()
async def start_app():
    ...

    # Wait for some users joining
    await asyncio.sleep(60)

    for session_id, session in app_context.sessions.items():

        cont = content.v0.Title(
            text="Game starts!"
        )
        # Show for this user
        await cont.show(session)
```

We will go through using contexts later.

### Synchronize multiple users

You might want to show a user
content based on other users
actions:

```python
@app.on_start()
async def start_app():
    n_users = 0
    @app.on_open()
    async def new_user():
        nonlocal n_users
        n_users += 1
        cont = content.v0.Title(
            text=f"You are {n_users}th user!"
        )
        await cont.show()
```

!!! tip

    Combine this with ``wait_input`` to
    have interactivity between users:

    ```python
    @app.on_start()
    async def start_app():
        messages = []
        @app.on_open()
        async def new_user():
            last_message = messages[-1] if messages else ""
            cont = content.v0.layouts.Column(
                contents=[
                    content.v0.Title(
                        text=f"Previous user said: {last_message}"
                    ),
                    content.v0.widgets.InputText(
                        submitText="Say"
                    ),
                ]
            )
            action = await cont.wait_input()
            messages.append(action["value"])
    ```

Alternatively, you can use app context
to structure your shared data (more later).

### Using Contexts

Contexts (in Miniappi's case) are global
variables which data depends on the scope.

There are two contexts in Miniappi:

- ``app_context``: Scoped for the current app
- ``user_context``: Scoped for the current user

The scope determines where the data inside the
context is accessible. Ie. a user scoped context
is only accessible from functions decorated with
``app.on_open()``, ``app.on_message()``, ``app.on_close()``,

Less talking and more showing:

```python
from miniappi import app_context, user_context

# This WILL raise an error:
app_context.sessions

@app.on_start()
async def start_app():
    # This won't raise an error:
    app_context.sessions

    # This WILL raise an error
    user_context.request_id

@app.on_open()
async def new_user():
    # These won't raise an error
    app_context.sessions
    user_context.request_id
```

This means that you can safely create
one app/user context and use that
all around your app, including in
modules, without constantly needing
to pass it around. Context is useful
for widely used data in your app.

You can also create your own context.
It uses Pydantic underneath:

```python
from miniappi import ContextModel

class AppContext(ContextModel):
    n_users: int = 0

class UserContext(ContextModel):
    username: str = ""

app_context = AppContext()
user_context = UserContext()

app = App(
    app_context=app_context,
    user_context=user_context
)

@app.on_start()
async def start_app():

    @app.on_open()
    async def new_user():
        app_context.n_users += 1
        user_context.username = "..."
```

!!! tip

    Specifying your own context won't override
    the default contexts. You can use both.

The default contexts have some useful attributes:

> miniappi.app_context

| Attribute | Type                | Description |
| --------- | ------------------- | ----------- |
| app       | App                 | App object  |
| sessions  | Dict[str, Session]  | Mapping of request IDs and their sessions (open connections) |
| extra     | Dict                | Custom data |

> miniappi.user_context

| Attribute  | Type                | Description |
| ---------- | ------------------- | ----------- |
| session    | Session             | User conntection object |
| request_id | str                 | ID of the session/connection |
| extra      | Dict                 | Custom data |

### Temporary handling

Sometimes you may want to handle
user actions differently based
on the state of your app, for example:

- Put new users to waiting list after game
  session has started

For such situations you can use ``temp``
method which enables you to create
callbacks for the duration of the
context manager:

```python
import asyncio

@app.on_start()
async def new_user(session):
    with app.temp() as temp:
        @temp.on_open()
        async def new_user():
            ...
        # Sync new users
        ... 
    # From now on, "new_user"
    # won't be run for new users
    ...
```

Here is an example of a waiting list:

```python
import asyncio

@app.on_start()
async def new_user(session):
    is_started = asyncio.Event()
    players = []
    with app.temp() as temp:
        @temp.on_open()
        async def new_player():
            cont = content.v0.widgets.InputText(
                placeholder="Player name",
                submitText="Join"
            )
            textbox = await cont.wait_input()
            name = textbox["value"]
            players.append(name)
            if len(players) < 5:
                await is_started.wait()
            else:
                is_started.set()
            cont = content.v0.Title(
                text="Game started!"
            )
            await cont.show()
            ... # Play the game

        # Wait till 5th player joins the game
        await is_started.wait()

    # From now on, the function
    # "new_player" won't be run
    # for new users but it
    # continues to run for the existing
    # users.

    # We will show waiting list
    # for new users
    with app.temp() as temp:
        @temp.on_open()
        async def new_users_to_waiting_list():
            cont = content.v0.Title(
                text="You are in a waiting list..."
            )
            await cont.show()
            ...
        ... # Play game
```

### Sending stream of data

For messaging apps, plotting apps or
other apps that rely on stream of data,
refreshing the whole UI for every new
message or record causes unnecessary
network burden and slows the app.

Instead of doing this:

```python

@app.on_open()
async def new_user(session):
    # Show data
    await content.v0.layouts.Row(
        contents=["first"]
    ).show()

    ... # Wait for data

    # Show updated data
    await content.v0.layouts.Row(
        contents=["first", "second"]
    ).show()

    # And some more data
    await content.v0.layouts.Row(
        contents=["first", "second", "third"]
    ).show()
```

you can use ``Feed``:

```python
from miniappi.ref import Feed

@app.on_open()
async def new_user(session):
    # Show data
    feed = Feed[str](["first"])
    await content.v0.layouts.Row(
        contents=feed
    ).show()

    ... # Wait for data

    # Show updated data
    await feed.append("second")

    # And some more data
    await feed.append("third")
```

When a feed is appended with new data,
it triggers push event to the UI.
It only sends the appended item but
the UI keeps the previous values in
memory.

If called in user context (ie. inside ``on_open``),
the event is sent only for the current user.
If called in app context (ie. inside ``on_start``),
the event is sent to all open user sessions.

If the list gets too big, the feed automatically
removes items. Having too big feed may slow down
the UI or make it unusable thus it is important
not to accumulate too much data in the UI. This
is limiting partly done in the app and partly in
the UI so that there is no need to send explicit
deletion events.

You can control the limiting with ``limit``
and ``method`` parameters:

```python
feed = Feed([], limit=20, method="fifo")
```

This feed can contain only 20 items and if more
are put, the items in the beginning of the
list (first appended) will be removed first.
You can also use ``lifo`` to remove those first
which were added last.
