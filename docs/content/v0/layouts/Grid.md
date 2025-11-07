
# Grid


Using this component:

```python
from miniappi.content.v0.layouts import Grid
Grid(...)
```
## Attributes

| attribute  | type      | description | required |
|------------|-----------|-------------|----------|
| cols | number | None | False |
| contents | array or ArrayReference | None | True |
| rows | number | None | False |

## Suplementary

### ArrayReference
```python
from miniappi.content.v0.layouts.grid import ArrayReference
```

| attribute  | type      | description | required |
|------------|-----------|-------------|----------|
| data | array | None | True |
| limit | number | None | True |
| method | string: <ul><li>'lifo'</li><li>'fifo'</li><li>'ignore'</li></ul> | None | True |
| reference | string | None | True |
| type | string | None | True |

