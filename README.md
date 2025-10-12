# Miniappi

[![Python test](https://github.com/Miksus/miniappi-python/actions/workflows/build.yml/badge.svg)](https://github.com/Miksus/miniappi-python/actions/workflows/build.yml)

## What is it?

This library is a Python client library for
[Miniappi app server](https://miniappi.com/).
Read more from the [Python documentation](https://python-docs.miniappi.com).

## Installation

Install with Pip:

```bash
pip install miniappi
```

Install with uv:

```bash
uv add miniappi
```

## Getting Started

```python
from miniappi import App, content

app = App()

@app.on_open()
async def run_user_open():
    cont = content.v0.Title(
        text="Hello world!"
    )
    await cont.show()

app.run()
```

Then follow the link to Miniappi server.

Read more from the [Miniappi documentation](https://python-docs.miniappi.com).
