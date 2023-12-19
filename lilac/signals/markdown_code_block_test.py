"""Test the Markdown Extractor signal."""

from ..schema import field
from ..splitters.text_splitter_test_utils import text_to_expected_spans
from .markdown_code_block import MarkdownCodeBlockSignal


def test_markdown_code_block_fields() -> None:
  signal = MarkdownCodeBlockSignal()
  signal.setup()
  assert signal.fields() == field(fields=[field('string_span', fields={'language': 'string'})])


def test_markdown_code_block() -> None:
  signal = MarkdownCodeBlockSignal()
  signal.setup()

  text = """
I am trying to add an extra field to my model form in Django.

```python
class MyForm(forms.ModelForm):
    extra_field = forms.CharField()
    class Meta:
        model = MyModel
        widgets = {
            'extra_field': forms.Textarea(attrs={'placeholder': u'Bla bla'}),
        }
```
However, it appears that the widget definition for 'extra_field' in the Meta class is ignored.

```py
class MyForm(forms.ModelForm):
    extra_field = forms.CharField(widget=forms.Textarea())
    class Meta:
        model = MyModel
```

Could you explain why my first approach does not work and what I am doing wrong?

Here is the console output:
```
fake output
```

"""
  markdown_blocks = list(signal.compute([text]))

  expected_spans = text_to_expected_spans(
    text,
    [
      (
        """```python
class MyForm(forms.ModelForm):
    extra_field = forms.CharField()
    class Meta:
        model = MyModel
        widgets = {
            'extra_field': forms.Textarea(attrs={'placeholder': u'Bla bla'}),
        }
```""",
        {'language': 'python'},
      ),
      (
        """```py
class MyForm(forms.ModelForm):
    extra_field = forms.CharField(widget=forms.Textarea())
    class Meta:
        model = MyModel
```""",
        {'language': 'py'},
      ),
      (
        """```
fake output
```""",
        {'language': ''},
      ),
    ],
  )

  assert markdown_blocks == [expected_spans]
