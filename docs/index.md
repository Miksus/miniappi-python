# Welcome to Miniappi (Package)

This is Miniappi's Python package for
communicating with [Miniappi server](https://miniappi.com).

## Install

Install from PyPI:

```bash
pip install miniappi
```

## Minimal example

```python
from miniappi import App, content

app = App()

@app.on_open()
async def new_user():
    cont = content.v0.Title(text="Hello World!")
    await cont.show()

app.run()
```

This should print something like the following:

```text
╭───────────────────────────────────────────────────────────────────────────╮
│ Miniappi is running.                                                      │
│ App link: https://miniappi.com/apps/0741f9ca-e719-4b77-9c07-96621bf9ebcb! │
╰───────────────────────────────────────────────────────────────────────────╯
```

Just follow the link to [Miniappi](https://miniappi.com) and you will find
your app.
