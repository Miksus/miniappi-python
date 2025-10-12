
# InputNumber


Using this component:

```python
from miniappi.content.v0.widgets import InputNumber
InputNumber(...)
```
## Attributes

| attribute  | type      | description | required |
|------------|-----------|-------------|----------|
| defaultValue | ['number', 'null'] | The default value for the input when not controlled by `modelValue`. | False |
| max | number | Maximum boundary value. | False |
| maxFractionDigits | number | The maximum number of fraction digits to use. Possible values are from 0 to 20; the default for plain number formatting is the larger of minimumFractionDigits and 3; the default for currency formatting is the larger of minimumFractionDigits and the number of minor unit digits provided by the [ISO 4217 currency code](https://www.six-group.com/en/products-services/financial-information/data-standards.html#scrollTo=maintenance-agency) list (2 if the list doesn't provide that information). | False |
| min | number | Minimum boundary value. | False |
| minFractionDigits | number | The minimum number of fraction digits to use. Possible values are from 0 to 20; the default for plain number and percent formatting is 0; the default for currency formatting is the number of minor unit digits provided by the [ISO 4217 currency code](https://www.six-group.com/en/products-services/financial-information/data-standards.html#scrollTo=maintenance-agency) list (2 if the list doesn't provide that information). | False |
| prefix | string | Text to display before the value. | False |
| showButtons | boolean | Displays spinner buttons. | False |
| step | number | Step factor to increment/decrement the value. | False |
| submitText | string | None | False |
| suffix | string | Text to display after the value. | False |

