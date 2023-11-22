import lilac as ll


class TestSignal(ll.TextSignal):
  """Test signal that computes the length of text, and whether it's all capitalized."""

  # The unique identifier for the signal. This must be globally unique.
  name = 'test_signal'
  # The display name will show up in the UI.
  display_name = 'text_len_and_capital'

  # Set the input type of the signal to text.
  input_type = ll.SignalInputType.TEXT

  def fields(self):
    return ll.field(
      fields={
        'len': 'int32',
        # See lilac.DataType for details on datatypes.
        'is_all_capital': 'boolean',
      }
    )

  def compute(self, data):
    for text in data:
      yield {
        'len': len(text),
        # Determine whether all the letters are capitalized.
        'is_all_capital': text.upper() == text,
      }


def main():
  print('hi')
  register_signals()
  ll.start_server(project_dir='./data')


def register_signals():
  """Registers all signals defined in the `signals` module."""
  ll.register_signal(TestSignal)


if __name__ == '__main__':
  main()
