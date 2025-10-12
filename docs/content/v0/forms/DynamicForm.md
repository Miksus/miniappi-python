
# DynamicForm


Using this component:

```python
from miniappi.content.v0.forms import DynamicForm
DynamicForm(...)
```
## Attributes

| attribute  | type      | description | required |
|------------|-----------|-------------|----------|
| fields | array | None | True |

## Suplementary

### FormField
```python
from miniappi.content.v0.forms.dynamic_form import FormField
```

| attribute  | type      | description | required |
|------------|-----------|-------------|----------|
| args | Dict[string,any] | None | False |
| default | any | None | False |
| label | string | None | True |
| name | string | None | True |
| type | string: <ul><li>'text'</li><li>'date'</li><li>'datetime'</li><li>'boolean'</li><li>'integer'</li><li>'submit'</li></ul> | None | True |
| value | any | None | False |


### Submit
```python
from miniappi.content.v0.forms.dynamic_form import Submit
```

| attribute  | type      | description | required |
|------------|-----------|-------------|----------|
| args | Dict[string,any] | None | False |
| default | any | None | False |
| label | string | None | True |
| name | string | None | True |
| type | string | None | True |
| value | any | None | False |

