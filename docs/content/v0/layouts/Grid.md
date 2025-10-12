
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
| contents | array or Reference[any[]] | None | True |
| rows | number | None | False |

## Suplementary

### Reference<any[]>
```python
from miniappi.content.v0.layouts.grid import Reference%3Cany%5B%5D%3E
```

| attribute  | type      | description | required |
|------------|-----------|-------------|----------|
| data | array | If given, the reference is initialized with given type | False |
| reference | string | ID of the reference | True |

