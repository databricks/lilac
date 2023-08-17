# Explore a dataset

```{tip}
[Explore popular datasets in Lilac on HuggingFace](https://huggingface.co/spaces/lilacai/lilac)
```

Exploring a dataset is often useful to understand what's inside a dataset, or even find glaring
dataset bugs.

## From the UI

```{tip}
[Follow along on HuggingFace with the `imdb` dataset](https://lilacai-lilac.hf.space/datasets#lilac/imdb)
```

After loading a dataset you'll be redirected to the dataset viewer:

<img src="../_static/dataset/dataset_explore.png"></img>

#### Items

The right hand side contains an infinite scroll panel where we can see the examples with their
metadata.

#### Schema

The left hand side contains the schema, which represents the columns.

If we open up the expand icon for the `label`, we'll see a histogram that shows us the distribution
of values for the feature:

<img width=360 src="../_static/dataset/dataset_stats.png"></img>

Here we can see that there are 75,000 examples with the label `pos` and 25,000 examples with the
label `neg`.

If we click on one of the bars of the histogram, we'll apply a filter with that label:

<img src="../_static/dataset/dataset_filter.png"></img>

#### Keyword search

Before we do advanced searching, like concept or semantic search, we can immediately use keyword
search by typing a keyword in the search box and choosing "keyword search":

<img width=360 src="../_static/dataset/dataset_keyword_search.png"></img>

This will add a search pill to add a filter for the keyword search, with the query bolded in
results. Filters are chained, so if you perform another keyword search it will find examples where
both keywords are present.

<img src="../_static/dataset/dataset_keyword_search_results.png"></img>

#### Sharing URLs

After clicking around and finding interested findings in datasets, we can share the URL to exactly
the view we are looking at by:

- Copying the URL
- Clicking the Copy URL Icon

<img src="../_static/dataset/dataset_copy_url_icon.png"></img>

The URL will have a hash-identifier that represents the UI state you are in.

## From Python

The Lilac Python API has 2 top-level methods which power the exploration from the UI:
[](#Dataset.select_rows) and [](#Dataset.select_groups). `select_rows` will select individual rows,
and `select_groups` will count values for each feature.

#### `select_rows`

```python
dataset = ll.get_dataset('local', 'imdb')
r = dataset.select_rows(['text', 'label'], limit=5)
print('Total number of rows', r.total_num_rows)

# Print the Panda dataframe representation.
print(r.df())

# Or print the results as an iterable of dicts:
for item in r:
  print(item)

```

Output:

```
Total number of rows 100000

text label
0  I rented I AM CURIOUS-YELLOW from my video sto...   neg
1  "I Am Curious: Yellow" is a risible and preten...   neg
2  If only to avoid making this type of film in t...   neg
3  This film was probably inspired by Godard's Ma...   neg
4  Oh, brother...after hearing about this ridicul...   neg

items:
{'text': 'I rented I AM CURIOUS-YELLOW from my video store because of all the controversy that surrounded it when it was first released in 1967. I also heard that at first it was seized by U.S. customs if it ever tried to enter this country, therefore being a fan of films considered "controversial" I really had to see this for myself.<br /><br />The plot is centered around a young Swedish drama student named Lena who wants to learn everything she can about life. In particular she wants to focus her attentions to making some sort of documentary on what the average Swede thought about certain political issues such as the Vietnam War and race issues in the United States. In between asking politicians and ordinary denizens of Stockholm about their opinions on politics, she has sex with her drama teacher, classmates, and married men.<br /><br />What kills me about I AM CURIOUS-YELLOW is that 40 years ago, this was considered pornographic. Really, the sex and nudity scenes are few and far between, even then it\'s not shot like some cheaply made porno. While my countrymen mind find it shocking, in reality sex and nudity are a major staple in Swedish cinema. Even Ingmar Bergman, arguably their answer to good old boy John Ford, had sex scenes in his films.<br /><br />I do commend the filmmakers for the fact that any sex shown in the film is shown for artistic purposes rather than just to shock people and make money to be shown in pornographic theaters in America. I AM CURIOUS-YELLOW is a good film for anyone wanting to study the meat and potatoes (no pun intended) of Swedish cinema. But really, this film doesn\'t have much of a plot.', 'label': 'neg'}
{'text': '"I Am Curious: Yellow" is a risible and pretentious steaming pile. It doesn\'t matter what one\'s political views are because this film can hardly be taken seriously on any level. As for the claim that frontal male nudity is an automatic NC-17, that isn\'t true. I\'ve seen R-rated films with male nudity. Granted, they only offer some fleeting views, but where are the R-rated films with gaping vulvas and flapping labia? Nowhere, because they don\'t exist. The same goes for those crappy cable shows: schlongs swinging in the breeze but not a clitoris in sight. And those pretentious indie movies like The Brown Bunny, in which we\'re treated to the site of Vincent Gallo\'s throbbing johnson, but not a trace of pink visible on Chloe Sevigny. Before crying (or implying) "double-standard" in matters of nudity, the mentally obtuse should take into account one unavoidably obvious anatomical difference between men and women: there are no genitals on display when actresses appears nude, and the same cannot be said for a man. In fact, you generally won\'t see female genitals in an American film in anything short of porn or explicit erotica. This alleged double-standard is less a double standard than an admittedly depressing ability to come to terms culturally with the insides of women\'s bodies.', 'label': 'neg'}
{'text': "If only to avoid making this type of film in the future. This film is interesting as an experiment but tells no cogent story.<br /><br />One might feel virtuous for sitting thru it because it touches on so many IMPORTANT issues but it does so without any discernable motive. The viewer comes away with no new perspectives (unless one comes up with one while one's mind wanders, as it will invariably do during this pointless film).<br /><br />One might better spend one's time staring out a window at a tree growing.<br /><br />", 'label': 'neg'}
{'text': "This film was probably inspired by Godard's Masculin, féminin and I urge you to see that film instead.<br /><br />The film has two strong elements and those are, (1) the realistic acting (2) the impressive, undeservedly good, photo. Apart from that, what strikes me most is the endless stream of silliness. Lena Nyman has to be most annoying actress in the world. She acts so stupid and with all the nudity in this film,...it's unattractive. Comparing to Godard's film, intellectuality has been replaced with stupidity. Without going too far on this subject, I would say that follows from the difference in ideals between the French and the Swedish society.<br /><br />A movie of its time, and place. 2/10.", 'label': 'neg'}
{'text': 'Oh, brother...after hearing about this ridiculous film for umpteen years all I can think of is that old Peggy Lee song..<br /><br />"Is that all there is??" ...I was just an early teen when this smoked fish hit the U.S. I was too young to get in the theater (although I did manage to sneak into "Goodbye Columbus"). Then a screening at a local film museum beckoned - Finally I could see this film, except now I was as old as my parents were when they schlepped to see it!!<br /><br />The ONLY reason this film was not condemned to the anonymous sands of time was because of the obscenity case sparked by its U.S. release. MILLIONS of people flocked to this stinker, thinking they were going to see a sex film...Instead, they got lots of closeups of gnarly, repulsive Swedes, on-street interviews in bland shopping malls, asinie political pretension...and feeble who-cares simulated sex scenes with saggy, pale actors.<br /><br />Cultural icon, holy grail, historic artifact..whatever this thing was, shred it, burn it, then stuff the ashes in a lead box!<br /><br />Elite esthetes still scrape to find value in its boring pseudo revolutionary political spewings..But if it weren\'t for the censorship scandal, it would have been ignored, then forgotten.<br /><br />Instead, the "I Am Blank, Blank" rhythymed title was repeated endlessly for years as a titilation for porno films (I am Curious, Lavender - for gay films, I Am Curious, Black - for blaxploitation films, etc..) and every ten years or so the thing rises from the dead, to be viewed by a new generation of suckers who want to see that "naughty sex film" that "revolutionized the film industry"...<br /><br />Yeesh, avoid like the plague..Or if you MUST see it - rent the video and fast forward to the "dirty" parts, just to get it over with.<br /><br />', 'label': 'neg'}
```

We can also apply a keyword search:

```python
r = dataset.select_rows(['text', 'label'],
                        searches=[ll.KeywordSearch(path='text', query='photography')],
                        limit=5)
```

Output:

```
                                                text label  \
0  I would put this at the top of my list of film...   neg
1  The premise of the movie has been explained an...   neg
2  photography was too jumpy to follow. dark scen...   neg
3  Yesterday was Earth Day (April 22, 2009) in th...   neg
4  In my book "Basic Instinct" was a perfect film...   neg

        text.substring_search(query=photography)
0    [{'__value__': {'start': 486, 'end': 497}}]
1  [{'__value__': {'start': 1256, 'end': 1267}}]
2       [{'__value__': {'start': 0, 'end': 11}}]
3  [{'__value__': {'start': 1059, 'end': 1070}}]
4    [{'__value__': {'start': 173, 'end': 184}}]
```

This will filter the results for where the keyword search is present, and add a column
`text.substring_search(query=photography)` to the dataframe, with the span offsetes of where the
query was found.

See [](#Dataset.select_rows) for more options.

#### `select_groups`

To count the number of positive and negative examples:

```python
groups = dataset.select_groups(leaf_path='label')

print(groups)
```

Output:

```
too_many_distinct=False counts=[('pos', 75000), ('neg', 25000)] bins=None
```

See [](#Dataset.select_groups) for more options.

#### `data_schema`

To get the schema and metadata for the dataset, call dataset.manifest():

```python
print(dataset.manifest())
```

Output:

```
namespace='local' dataset_name='imdb' data_schema={
  "fields": {
    "text": {
      "dtype": "string"
    },
    "label": {
      "dtype": "string"
    },
    "__hfsplit__": {
      "dtype": "string"
    }
  }
} num_items=100000
```
