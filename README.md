# Miniappi

## What is it?

This library is a Python client library for
Miniappi app server. It handles requests


## Installation

```bash
pip install miniappi
```

## Getting Started

```python
from miniappi import App, content

app = App()

@app.on_start()
async def run_start():
    print("App started")

@app.on_open()
async def run_user_open():
    await content.v0.

app.run()
```
