
# Row


Using this component:

```python
from miniappi.content.v0.layouts import Row
Row(...)
```
## Attributes

| attribute  | type      | description | required |
|------------|-----------|-------------|----------|
| contents | array or ArrayReference | None | True |

## Suplementary

### ArrayReference
```python
from miniappi.content.v0.layouts.row import ArrayReference
```

| attribute  | type      | description | required |
|------------|-----------|-------------|----------|
| data | array | None | True |
| limit | number | None | True |
| method | string: <ul><li>'lifo'</li><li>'fifo'</li><li>'ignore'</li></ul> | None | True |
| reference | string | None | True |
| type | string | None | True |

