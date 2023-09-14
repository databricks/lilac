# Query a dataset (Python)

After enriching a dataset with concepts and signals, we can issue queries to the dataset to search
and filter the data.

This guide will be a Python-only guide as these queries power the UI. For more details on exploring
a dataset with the UI, see [Explore a dataset](./dataset_explore.md).

## The `Dataset` object

Before we can query a dataset, we need to get a handle to the dataset, an instance of [](#Dataset).

```python
import lilac as ll

# Set the project path globally. For more information, see the Projects guide.
ll.set_project_path('~/my_project')

dataset = ll.get_dataset('local', 'imdb')
```

## Manifest and Schema

Datasets in Lilac have a `manifest()` method which returns a [](#DatasetManifest) object containing
metadata about the dataset, the [](#Schema), the [](#Source) that was used to load the dataset, and
the number of rows.

The [](#DatasetManifest.data_schema) property on the manifest will give us information about fields,
their dtypes, which signals produced it, and other metadata.

In this example, we've enriched the `imdb` dataset's `text` field with the `gte-small` embedding,
the `pii` signal, and the `text_statistics` signal.

```python
manifest = dataset.manifest()
print(manifest)
```

Output:

```
DatasetManifest(namespace='local', dataset_name='imdb', data_schema={
  "fields": {
    "text": {
      "fields": {
        "pii": {
          "fields": {
            "emails": {
              "repeated_field": {
                "dtype": "string_span"
              }
            },
            "ip_addresses": {
              "repeated_field": {
                "dtype": "string_span"
              }
            },
            "secrets": {
              "repeated_field": {
                "dtype": "string_span"
              }
            }
          },
          "signal": {
            "signal_name": "pii"
          }
        },
        "gte-small": {
          "repeated_field": {
            "fields": {
              "embedding": {
                "dtype": "embedding"
              }
            },
            "dtype": "string_span"
          },
          "signal": {
            "signal_name": "gte-small"
          }
        },
        "text_statistics": {
          "fields": {
            "num_characters": {
              "dtype": "int32"
            },
            "readability": {
              "dtype": "float32"
            },
            "log(type_token_ratio)": {
              "dtype": "float32"
            },
            "frac_non_ascii": {
              "dtype": "float32",
              "bins": [
                [
                  "Low",
                  null,
                  0.15
                ],
                [
                  "Medium",
                  0.15,
                  0.3
                ],
                [
                  "High",
                  0.3,
                  null
                ]
              ]
            }
          },
          "signal": {
            "signal_name": "text_statistics"
          }
        }
      },
      "dtype": "string"
    },
    "label": {
      "dtype": "string"
    },
    "__hfsplit__": {
      "dtype": "string"
    }
  }
}, source=HuggingFaceSource(dataset_name='imdb', config_name=None, split=None, sample_size=None, revision=None, load_from_disk=False), num_items=100000)
```

You'll notice that there is a nested hierarchy of data, which reflects signals and embeddings to be
put **under** the enriched field so that we can align counts properly.

### Paths

When we query the dataset, fields are identified by their _path_. Paths represent the hierarchy of
the data, and can either be expressed as a tuple, or as a period-separated string.

In the example above, the `emails` field under `pii` can be accessed with:

- `('text', 'pii', 'emails', '*')`
- `'text.pii.emails.*'`

You'll notice there is a `*` in the paths. This is a _path wildcard_, which refers to a field that
is repeated (e.g. a list of values). By selecting with a `*`, we will get all of the values under
the emails field, which is a list of emails.

If we want to see all of the leaf paths from the schema, we can use [](#Schema.leafs), which returns
a dictionary mapping a path to a [](#Field).

```python
# Get the dictionary keys from the leafs.
leaf_paths = manifest.data_schema.leafs.keys()

print(leaf_paths)
```

Output:

```python
dict_keys([
  ('text',),
  ('label',),
  ('__hfsplit__',),
  ('text', 'gte-small', '*'),
  ('text', 'text_statistics', 'num_characters'),
  ('text', 'text_statistics', 'readability'),
  ('text', 'text_statistics', 'log(type_token_ratio)'),
  ('text', 'text_statistics', 'frac_non_ascii'),
  ('text', 'pii', 'emails', '*'),
  ('text', 'pii', 'ip_addresses', '*'),
  ('text', 'pii', 'secrets', '*'),
  ('text', 'gte-small', '*', 'embedding')
])
```

Notice that the paths contain the fields from the source, as well as the paths from any enrichments.

## Queries

Datasets have two top-level methods for querying:

- [](#Dataset.select_rows): Select individual rows according to searches, filters, sorts, limits,
  and offsets.
- [](#Dataset.select_groups): Select groups and their counts. This is similar to the SQL
  `GROUP BY feature COUNT(*)`. This method gives us a histogram of feature values and their counts,
  with filters applied.

### select_rows

[](#Dataset.select_rows) will return individual rows, applying searches, filters, sorts, and limits.

The result of `select_rows` is a [](#SelectRowsResult), a generator that yields an iterable of
dictionaries for each row. We can also get the result as a Pandas Dataframe by calling
[](#SelectRowsResult.df).

Let's take a look at each parameter to `select_rows`.

#### `columns`

`columns` is a a list of paths to select. This is analogous the the `SELECT` clause in SQL.

Let's select the first row, but only the `text` and `label` fields.

```python
rows = dataset.select_rows(columns=['text', 'label'], limit=1)
print(list(rows))
```

Output:

```
[{
  'text': "I can't believe that those praising this movie herein aren't thinking of some other film. I was prepared for the possibility that this would be awful, but the script (or lack thereof) makes for a film that's also pointless. On the plus side, the general level of craft on the part of the actors and technical crew is quite competent, but when you've got a sow's ear to work with you can't make a silk purse. Ben G fans should stick with just about any other movie he's been in. Dorothy S fans should stick to Galaxina. Peter B fans should stick to Last Picture Show and Target. Fans of cheap laughs at the expense of those who seem to be asking for it should stick to Peter B's amazingly awful book, Killing of the Unicorn.",
  'label': 'neg'}]
```

#### `searches`

`searches` is a list of searches to apply. Searches sort the results by a query, and sometimes
filter them.

Searches can be one of:

- [](#ConceptSearch): Rank the results according to the concept score, descending. This type of
  search does not filter the results as the score is not computed for each result. This allows us to
  search by a concept as we refine a concept. This requires us to have an embedding computed over
  the given column first. See [Dataset Concepts](./dataset_concepts.md) for more.
- [](#SemanticSearch): Rank the results according to semantic similarity. The embedding is computed
  for the query, and results are ranked by dot product similarity.
- [](#KeywordSearch): Filter the results by whether the keyword is present. This is a
  case-insensitive exact search.

Let's search for non-english `text` values using the built-in `non-english` concept.

```python
rows = dataset.select_rows(
  columns=['text', 'label'],
  searches=[
    ll.ConceptSearch(
      path='text',
      concept_namespace='lilac',
      concept_name='non-english',
      embedding='gte-small')
  ],
  limit=1)

print(list(rows))
```

Output:

```
[{
  'text': 'In Nordestina, a village in the middle of nowhere in Pernambuco, Antônio (Gustavo Falcão) is the youngest son of his mother, who had uninterruptedly cried for five years. When he is a young man, he falls in love for Karina (Mariana Ximenes), a seventeen years old teenager that dreams to see the world and becomes an actress. Antônio promises Karina to bring the world to Nordestina, and once in Rio de Janeiro, he participates of a sensationalist television show and promises to travel to the fifty years ahead in the future or die for love with a deadly machine he had invented. Fifty years later, Antônio (Paulo Autran) tries to fix what was wrong in his travel.<br /><br />"A Máquina" is one of the best Brazilian movies I have recently seen. The refreshing and original story is a poetic and magic fable of love that will certainly thrill the most skeptical and tough viewer, in a unique romance. The direction is excellent; the screenplay is awesome; the cinematography and colors are magnificent; the cast leaded by Gustavo Falcão, the icon Paulo Autran and Mariana Ximenes is fantastic, with marvelous lines; the soundtrack has some beautiful Brazilian songs highlighting Geraldo Azevedo and Rento Rocha\'s "Dia Branco". If this movie is distributed overseas, please thrust me and rent it or buy the DVD because I bet you will love the story that will bring you into tears. My vote is nine.<br /><br />Title (Brazil): "A Máquina \x96 O Combustível é o Amor" ("The Machine \x96 The Fuel is Love")',
  'label': 'pos',
  'text.lilac/non-english/labels': nan,
  'text.lilac/non-english/gte-small': [
    {'__value__': {'start': 0, 'end': 399}, 'score': 0.21467934175612693},
    {'__value__': {'start': 350, 'end': 750}, 'score': 0.06376289702765257},
    {'__value__': {'start': 703, 'end': 1099}, 'score': 0.2161880253170404},
    {'__value__': {'start': 1054, 'end': 1453}, 'score': 0.24250582473635335},
    {'__value__': {'start': 1407, 'end': 1496}, 'score': 0.8338815910868351}
  ]
}]
```

You'll notice that the result will have the concept scores for a set of spans, given by `start` and
`end` which refer to the character offsets in the text.

The results are ranked by the _highest_ score for any span in the document, in this case 0.83 with
the offsets `(1407, 1496)`.

#### `filters`

`filters` is a list of filters to apply to the results. Filters give more control than searches as
we can filter by the any source field or the output of any signal.

Types of filters:

- Binary ops: Compares a feature to a particular value. This is expressed as a tuple, with supported
  comparators: `equals`, `not_equal`, `greater`, `greater_equal`, `less`, `less_equal`. Example:
  `('label', 'equals', 'pos')`.
- Unary ops: Only `exists` is supported. Used for checking whether a sparse feature has a value for
  a particular row. Example: `('label', 'exists')`.
- List ops: Filters results where a list value contains a particular value. Example:
  `('x', 'in', 'list_feature')`

Let's find the first example that is labeled `pos`.

```python
rows = dataset.select_rows(
  columns=['text', 'label'],
  filters=[('label', 'equals', 'pos')],
  limit=1)
print(list(rows))
```

Output:

```
[{
  'text': 'I haven\'t seen this movie in about 5 years, but it still haunts me. <br /><br />When asked about my favorite films, this is the one that I seem to always mention first. There are certain films (works of art like this film, "Dark City", and "Breaking the Waves") that seem to touch a place within you, a place so protected and hidden and yet so sensitive, that they make a lifelong impression on the viewer, not unlike a life-changing event, such as the ending of a serious relationship or the death of a friend... This film "shook" me when I first saw it. It left me with an emotional hangover that lasted for several days.',
  'label': 'pos'
}]
```

Now, let's find an example with an email address. `pii.emails` is sparse, so we will use `exists`.

```python
rows = dataset.select_rows(
  columns=['text', 'label', ('text', 'pii', 'emails', '*')],
  filters=[(('text', 'pii', 'emails', '*'), 'exists')],
  limit=1)
print(list(rows))
```

Output (actual email redacted from text):

```
[{
  'text': "I know this sounds odd coming from someone born almost 15 years after the show stopped airing, but I love this show. I don't know why, but I enjoy watching it. I love Adam the best. The only disappointing thing is that the only place I found to buy the seasons on DVD was in Germany, and that was only the first two seasons. That is disappointing, but that's OK. I'll keep looking online. If anyone has any tips on where to buy the second through 14th seasons, please email me at ______________@yahoo.com. I already own the first one. The only down side is that the DVDs being from Germany, they only play on my portable DVD player and my computer. Oh well. I still own it!",
  'label': 'pos',
  'text.pii.emails.*': [{
    '__value__': {'start': 480, 'end': 504}}
  ]
}]
```

#### `sort_by` and `sort_order`

We can also sort the results by any field by using `sort_by` and `sort_order`.

Let's sort the results by `text_statistics.readability_score`, which computes the textacy
readability score for each document. This assumes that the `text_statistics` signal has been run
over `text`.

```python
rows = dataset.select_rows(
  columns=['text', ('text', 'text_statistics', 'readability')],
  sort_by=[('text', 'text_statistics', 'readability')],
  sort_order='DESC',
  limit=1)
print(list(rows))
```

```
[{
  'text': "To some, this Biblical film is a story of judgment and condemnation... Others see it as a story of grace, restoration, and hope... It is actually both \x96 Henry King illustrates the portrait of a mighty monarch almost destroyed by his passion, his downward spiral of sin, and his upward climb of healing..<br /><br />'David and Bathsheba' is an emotional movie full of vividly memorable characters who attain mythic status while retaining their humanity... Henry King handles the powerful story, taken from the Old Testament, with skill...<br /><br />David, 'the lion of Judah,' having stormed the walls of Rabgah, saves the life of one of his faithful warriors Uriah (Kieron Moore), and returns to Jerusalem... <br /><br />Back at his court, his first wife complains of neglect, and offends him for being a shepherd's son, distinguishing herself for being the daughter of King Saul...<br /><br />One evening, and while walking on the terrace of his palace which evidently held a commanding view of the neighborhood, David's eyes happened to alight upon a young lady who was taking a refreshing bath... She was beautiful and attractive... David could not take his eyes off her... He finds out later on that she was the wife of one of his officers... <br /><br />Sending for her, he discovers that she, too, is unhappy in her marriage... By this point, it's apparent that David's intentions shift from an interest in taking Bathsheba as a wife, to just plain taking Bathsheba... As usual, sin had its consequences, and David hadn't planned on that possibility...<br /><br />When a drought sweeps the land and there is a threat of famine, David suspects that the Lord is punishing him and his people for his sin... But when Bathsheba tells him that she is pregnant and fears that she may be stoned to death according to the law of Moses, David tries to cover up his sin... <br /><br />He sends word to Joab, the commander of his army, and ordered him to send to him Bathsheba's husband... David did something that was abominable in God's sight... He sends the man to the front line where he would be killed... <br /><br />The soldier is indeed killed and with him out of the way, David marries his beloved Bathsheba in full regal splendor...<br /><br />God punishes the couple when Bathsheba's child dies soon after birth... Meanwhile, a mighty famine has spread throughout the land and the Israelites - led by Nathan - blame the King for their plight... They storm the palace and demand that Bathsheba pays for her sin...<br /><br />Peck plays the compassionate king whose lustful desire outweighed his good sense and integrity.. <br /><br />Hayward as Bathsheba, is a sensitive woman who begins to believe that every disaster occurring in her life is the direct result of her adultery... The sequence of her bath which could have been a great moment in Biblical film history, is badly mishandled, and the viewers eyes are led briefly to Hayward's face and shoulders...<br /><br />Raymond Massey appeared as Nathan the Prophet, sent by God to rebuke David after his adultery with Bathsheba; Gwyneth Verdon is Queen Michal who tries to resist the ambition and greed that have become integral to David's personality and kingship; ex-silent screen idol, Francis X. Bushman, had a brief part as King Saul... <br /><br />The best moments of the film were: The Ark en route to its permanent home when God breaks a young soldier who tries to touch the sacred object; the defining moment in David's life when he confesses his sin and is prepared to accept his punishment of death; and for the film's climax, inserting it as a flashback, David remembering his fight with the giant Goliath... <br /><br />With superb color photography and a masterly music score, 'David and Bathsheba' won Oscar nominations in the following categories: Music Scoring, Art and Set Direction, Cinematography, Story and Screenplay, and Costume Design..",
  'text.text_statistics.readability': 342.50909423828125}]
```

#### `limit` and `offset`

Just like SQL, we can limit and offset results using `limit` and `offset`.

```python
rows = dataset.select_rows(columns=['text'], limit=1, offset=100)
print(list(rows))
```

Output:

```
[{'text': "If I had not read Pat Barker's 'Union Street' before seeing this film, I would have liked it. Unfortuntately this is not the case. It is actually my kind of film, it is well made, and in no way do I want to say otherwise, but as an adaptation, it fails from every angle.<br /><br />The harrowing novel about the reality of living in a northern England working-class area grabbed hold of my heartstrings and refused to let go for weeks after I had finished. I was put through tears, repulsion, shock, anger, sympathy and misery when reading about the women of Union Street. Excellent. A novel that at times I felt I could not read any more of, but I novel I simply couldn't put down. Depressing yes, but utterly gripping.<br /><br />The film. Oh dear. Hollywood took Barker's truth and reality, and showered a layer of sweet icing sugar over the top of it. A beautiful film, an inspiring soundtrack, excellent performances, a tale of hope and romance...yes. An adaptation of 'Union Street'...no.<br /><br />The women of Union Street and their stories are condensed into Fonda's character, their stories are touched on, but many are discarded. I accept that some of Barker's tales are sensitive issues and are too horrific for mass viewing, and that a film with around 7 leading protagonists just isn't practical, but the content is not my main issue. The essence and the real gut of the novel is lost - darkness and rain, broken windows covered with cardboard, and the graphically described stench of poverty is replaced with sunshine, pretty houses, and a twinkling William's score.<br /><br />If you enjoyed the film for its positivity and hope in the face of 'reality', I advise that you hesitate to read the book without first preparing yourself for something more like 'Schindler's List'...but without the happy ending."}]
```

#### `combine_columns`

By default, the results of rows are returned flat, with each path as a top-level feature.

However, sometimes we would like to get a deeply nested hierarchical resolve, with enrichments
living underneath their original document.

We can use `combine_columns=True` to return a nested result.

```python
rows = dataset.select_rows(
  columns=['text', 'label', ('text', 'pii', 'emails', '*')],
  filters=[(('text', 'pii', 'emails', '*'), 'exists')],
  combine_columns=True,
  limit=1)

print(list(rows))
```

Output:

```
[{
  'text': {
    '__value__': "I agree with most if not all of the previous commenter's Tom (bighouseaz@yahoo.com). The Zatoichi series is a great character study combined with great sword fighting and excitement.<br /><br />I have seen Zatoichi 1-13,15,16; I believe 14 has not been released on Zone 1 (usa). Zatoichi the Outlaw was disappointing. The story line was complicated, and seemed to be a hodgepodge of many previous Zatoichi story lines. At one point, I was wondering if I was not seeing a remake of a previous Zatoichi film.<br /><br />This film was disappointing because it started to depend on effects (a head rolling, limbs severed, blood) and less on the nobility of the Zatoichi character. All the previous films succeeded based on the storyline and action, and won a great following without having to resort to effects.<br /><br />I am just hoping that the remaining Zatoichi films do NOT follow the same trend. This is the first Zatoichi film from his studio. I highly recommend all the previous Zatoichi films -- and recommend them.",
    'pii': {
      'emails': [{
        '__value__': {'start': 62, 'end': 82}}
      ],
      'ip_addresses': [],
      'secrets': []
    },
    'text_statistics': {
      'num_characters': 1022,
      'readability': 12.02110481262207,
      'log(type_token_ratio)': 0.8965761065483093,
      'frac_non_ascii': 0.0
    }
  },
  'label': 'neg'
}]
```

### select_groups

[](#Dataset.select_groups) will return _counts_ for each feature value of a given feature. This lets
us power histograms, and is similar to the SQL `GROUP BY feature COUNT(*)`.

The result of `select_groups` is a [](#SelectGroupsResult), an object with:

- `counts`: a list counts for each feature value. For example: `[('pos', 75000), ('neg', 25000)]`.
- `bins`: A set of named bins for floating point values. This is useful for bucketing floats into
  discrete buckets for counting. By default, we will take the min and max of the feature value for
  floating point values, and chunk into 10 bins.
- `too_many_distinct`: When there are too many distinct values for a feature, we will not return
  results to avoid OOMing.

`select_groups` takes many similar arguments as `select_rows` for filtering, sorting, and limiting.
The API is identical.

- `leaf_path`: The path to count groups for.
- `filters`: A list of filters to apply before counting. See [Filters](#filters) for more.
- `filters`: A list of filters to apply before counting. See [Filters](#filters) for more.
- `sort_by`: One of `count` or `value`. When sorting by count, we return the groups sorted by their
  total count. When sorting by value, we sort by the actual feature value.
- `sort_order`: One of `DESC` or `ASC`.
- `limit`: Limit the number of groups. Useful when the cardinality of a feature is very high.
- `bins`: Binned values for continuous features.

Let's count the positive and negative labels in the `imdb` dataset.

```python
groups = dataset.select_groups(leaf_path='label')
print(groups)
```

Output:

```
SelectGroupsResult(
  counts=[('pos', 75000), ('neg', 25000)],
  bins=None,
  too_many_distinct=False)
```

We can see that this dataset is skewed towards positive labels.

#### bins

Bins can be very useful to bucket continuous values into useful groups that are named, instead of
relying on the default bins of size 10.

Let's see what the result looks like for `readability_score`, a floating point continuous value with
the default, automatic binning of 10 groups.

```python
groups = dataset.select_groups(
  leaf_path=('text', 'text_statistics', 'readability'))
print(groups)
```

```
SelectGroupsResult(
  counts=[
    ('0', 86110),
    ('1', 12522),
    ('2', 798),
    ('3', 350),
    ('4', 122),
    ('5', 39),
    ('6', 32),
    ('7', 13),
    ('8', 6),
    ('14', 2),
    ('12', 2),
    ('9', 2),
    ('10', 1),
    ('11', 1)
  ],
  bins=[
    ('0', None, 16.878638648986815),
    ('1', 16.878638648986815, 40.13795690536499),
    ('2', 40.13795690536499, 63.39727516174315),
    ('3', 63.39727516174315, 86.65659341812133),
    ('4', 86.65659341812133, 109.91591167449951),
    ('5', 109.91591167449951, 133.17522993087766),
    ('6', 133.17522993087766, 156.43454818725584),
    ('7', 156.43454818725584, 179.69386644363402),
    ('8', 179.69386644363402, 202.9531847000122),
    ('9', 202.9531847000122, 226.21250295639038),
    ('10', 226.21250295639038, 249.47182121276853),
    ('11', 249.47182121276853, 272.7311394691467),
    ('12', 272.7311394691467, 295.9904577255249),
    ('13', 295.9904577255249, 319.24977598190304),
    ('14', 319.24977598190304, None)
  ],
  too_many_distinct=False)
```

The counts here will give us a string key that matches into the bins for the range.

That's a lot of bins! And they are not very meaningful as we have split the max and min into 10
equal sized buckets.

Now, using bins, let's make 3 bins for `(Inf, 100), (100, 200], (200, Inf)`

```python
groups = dataset.select_groups(
  leaf_path=('text', 'text_statistics', 'readability'),
  bins=[100, 200]
)
print(groups)
```

Output:

```
SelectGroupsResult(
  too_many_distinct=False,
  counts=[
    ('0', 99869),
    ('1', 122),
    ('2', 9)],
  bins=[
    ('0', None, 100.0),
    ('1', 100.0, 200.0),
    ('2', 200.0, None)
  ])
```

Already this is much nicer, but let's name them `LOW`, `MEDIUM`, and `HIGH`.

```python
groups = dataset.select_groups(
  leaf_path=('text', 'text_statistics', 'readability'),
  bins=[
    ('LOW', None, 100),
    ('MEDIUM', 100, 200),
    ('HIGH', 200, None)
  ]
)
print(groups)
```

Output:

```
SelectGroupsResult(
  counts=[
    ('LOW', 99869),
    ('MEDIUM', 122),
    ('HIGH', 9)
  ],
  bins=[
    ('LOW', None, 100.0),
    ('MEDIUM', 100.0, 200.0),
    ('HIGH', 200.0, None)
  ],
  too_many_distinct=False)
```
