<h3 align="center" style="font-size: 20px; margin-bottom: 4px">Curate better data for LLMs</h3>
<p align="center">
    <a href="https://discord.gg/jNzw9mC8pp">
        <img alt="Discord" src="https://img.shields.io/discord/1135996772280451153?label=Join%20Discord" />
    </a>
    <a href="https://github.com/lilacai/lilac">
      <img src="https://img.shields.io/github/stars/lilacai/lilac?style=social" />
    </a>
    <a href="https://twitter.com/lilac_ai">
      <img src="https://img.shields.io/twitter/follow/lilac_ai" alt="Follow on Twitter" />
    </a>
</p>

Lilac is an open-source tool that enables AI practitioners to improve their apps by improving their
data.

[Try Lilac on HuggingFace Spaces](https://lilacai-lilac.hf.space/datasets#lilac/OpenOrca-100k),
where we've preloaded popular datasets like OpenOrca. Try a semantic search for "As a language
model" on the OpenOrca dataset!

**Lilac can:**

- Browse datasets with text data.
- Annotate fields with structured metadata using [Signals](signals/signals.md), for instance
  near-duplicate and personal information (PII) detection.
- Use exact and semantic searches to find and tag specific slices of data.
- Create and refine [Concepts](concepts/concepts.md) to precisely target a type or style of text.
- Detect and remove duplicate or near-duplicate data.
- Filter and export your curated dataset for downstream applications.

<div align="center">
  <iframe width="672" height="378" src="https://www.youtube.com/embed/RrcvVC3VYzQ?si=K-qRY2fZ_RAjFfMw" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>
</div>
<br>
<br>
<h3>Core features</h3>
<table style="border-spacing:0">
  <tr>
    <td style="width:200px;padding-right:10px;">
      <h4>Semantic and keyword search</h4>
      <p style="color:rgb(75,75,75)">Query large datasets instantaneously</p>
      <p><a href="https://lilacai-lilac.hf.space/datasets#lilac/OpenOrca-100k&query=%7B%22searches%22%3A%5B%7B%22path%22%3A%5B%22response%22%5D%2C%22type%22%3A%22semantic%22%2C%22query%22%3A%22hacking%20a%20computer%22%2C%22embedding%22%3A%22gte-small%22%7D%5D%7D">Try it →</a></p>
    </td>
    <td><video loop muted autoplay controls src="_static/welcome/semantic-search.mp4"></video></td>
  </tr>
</table>

<br/>
<br/>

<table style="border-spacing:0">
  <tr>
    <td style="width:200px;padding-left:10px;">
      <h4>Dataset insights</h4>
      <p style="color:rgb(75,75,75)">See a mile-high overview of the dataset</p>
      <p><a href="https://lilacai-lilac.hf.space/datasets#lilac/OpenOrca-100k&insightsOpen=true">Try it →</a></p>
    </td>
    <td><video loop muted autoplay controls src="_static/welcome/insights.mp4"></video></td>
  </tr>
</table>

<br/>
<br/>

<table style="border-spacing:0">
  <tr>
    <td style="width:200px;padding-left:10px;">
      <h4>PII, duplicates, language detection, or add your own signal</h4>
      <p style="color:rgb(75,75,75)">Enrich natural language with structured metadata</p>
      <p><a href="https://lilacai-lilac.hf.space/datasets#lilac/OpenOrca-100k&query=%7B%22filters%22%3A%5B%7B%22path%22%3A%5B%22question%22%2C%22pii%22%2C%22emails%22%2C%22*%22%5D%2C%22op%22%3A%22exists%22%7D%5D%7D">Find emails →</a></p>
    </td>
    <td><video loop muted autoplay controls src="_static/welcome/signals.mp4"></video></td>
  </tr>
</table>

<br/>
<br/>

<table style="border-spacing:0">
  <tr>
    <td style="width:200px;padding-left:10px;">
      <h4>Make your own concepts</h4>
      <p style="color:rgb(75,75,75)">Curate a set of concepts for your business needs</p>
      <p><a href="https://lilacai-lilac.hf.space/concepts#lilac/profanity">Try a concept→</a></p>
    </td>
    <td><video loop muted autoplay controls src="_static/welcome/concepts.mp4"></video></td>
  </tr>
</table>

<br/>
<br/>

<table style="border-spacing:0">
  <tr>
    <td style="width:200px;padding-left:10px;">
      <h4>Download the enriched data</h4>
      <p style="color:rgb(75,75,75)">Continue working in your favorite data stack</p>
    </td>
    <td><video loop muted autoplay controls src="_static/welcome/download.mp4"></video></td>
  </tr>
</table>
