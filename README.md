# Japanese grammar examples in *1Q84*

An offline, searchable HTML concordance of all **341 L1 expression families** in the Tsutsuji Japanese functional-expression dictionary, with up to ten distinct example sentences per family from Haruki Murakami's *1Q84*, BOOK1–BOOK3.

Download [the HTML report](1Q84_L1_grammar_examples.html) and open it in a browser. It includes a grammar index, search, example-count filters, expandable entries, highlighted matches, and book/chapter/paragraph references. No server or internet connection is needed to read it.

L1 is a layer of the dictionary's expression hierarchy, not a proficiency level. The report searches each L1 family through its registered L9 spellings and grammatical variants as well as its L1 base expression.

## Contents

| File | Purpose |
| --- | --- |
| `1Q84_L1_grammar_examples.html` | The generated, self-contained report |
| `build_novel_examples.py` | EPUB extraction, dictionary matching, and HTML generation |
| `novel_report_template.html` | HTML, CSS, and browser-side search/filter interface |
| `requirements.txt` | Python dependencies |
| `.gitignore` | Excludes source books, dictionary files, and intermediate data |

The source EPUB, Tsutsuji XML/database, original L1–L9 lists, and intermediate `matches.json` are **not included**. The report necessarily includes its selected novel excerpts and dictionary-derived labels.

The repository's existing CC0 license does not replace the separate rights and license terms for novel excerpts, Tsutsuji-derived material, or dependencies described below.

## Results in the included report

| Measure | Count |
| --- | ---: |
| Narrative chapters searched | 79 |
| Extracted sentence units | 38,407 |
| Distinct dictionary surface strings searched | 15,887 |
| L1 families included | 341 |
| Families with ten examples | 227 |
| Families with one to nine examples | 75 |
| Families with no accepted match | 39 |
| Example excerpts displayed | 2,590 |

Counts reflect the supplied EPUB, Tsutsuji 1.1u, and the matching rules below. They are counts of automatic candidates, not human-verified occurrences of particular grammatical senses.

## Reproduce the report

Use Python 3.10 or later. The generator was run with Python 3.12, Janome 0.5.2, and lxml 6.1.1.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

python build_novel_examples.py \
  --epub "/path/to/1Q84 (全三冊).epub" \
  --dictionary "/path/to/tsutsuji1.1.xml" \
  --output-dir outputs/1q84-l1
```

On Windows, activate the environment with `.venv\Scripts\activate` and enter the generation command on one line.

Provide your own local source files. The generator reads them but does not download or upload them. It writes `1Q84_L1_grammar_examples.html` and an intermediate `matches.json` into the chosen output directory. The latter contains selected excerpts and per-entry statistics and is ignored by Git.

To render an existing intermediate file again without re-reading the novel or dictionary:

```sh
python build_novel_examples.py --render-only --output-dir outputs/1q84-l1
```

The template defaults to `novel_report_template.html` beside the script and can be changed with `--template`. Run `python build_novel_examples.py --help` for all options.

This extractor targets the particular three-book EPUB used for this analysis. It expects `toc.ncx`, chapter navigation labels containing `第…章`, 79 chapter files, and two initial nonblank heading/subtitle paragraphs per chapter. Different EPUB editions may need changes to `corpus()`. The generator also expects the 341 L1 entries in the supplied Tsutsuji version. EPUB paragraph references are not print-edition page numbers.

## Method

1. **Read the hierarchy.** Parse Tsutsuji's XML and collect each L1 ID, its base expression, its immediate L2 meaning labels, and every descendant L9 surface form. Remove the dictionary's segmentation dots. Retain all 341 L1 families, including those with no match. The Japanese meaning labels are dictionary metadata, not an inferred interpretation of each sentence.
2. **Extract narrative text.** Open the EPUB as a ZIP archive and follow the 79 chapter links in its NCX table of contents, in reading order. Exclude covers, contents pages, and other front matter. Remove ruby-reading and ruby-parenthesis elements while retaining their base characters and following text. Concatenate inline text without injecting spaces into Japanese words.
3. **Segment sentence excerpts.** Split on `。！？!?`, including within dialogue. When a final quoted sentence is followed by a reporting clause, retain the clause with that sentence. Retain original quotation marks and final unpunctuated paragraph fragments. Consequently, an excerpt can begin or end inside an existing quotation, and punctuation-based units are not always a single syntactic sentence. Number paragraphs by their original `<p>` position, including blank paragraphs, and number sentence units within each paragraph.
4. **Find literal surface forms efficiently.** Build an Aho–Corasick multi-pattern matcher over the collected forms. Search the unchanged extracted text, without converting kana to kanji, changing scripts, fuzzy matching, or inventing paraphrases. Kanji and inflected alternatives are found only when registered in the dictionary.
5. **Check morphology.** Tokenize each candidate sentence with Janome and its bundled IPADIC dictionary. Require both ends of each match to coincide with token boundaries. An explicit exception recognizes `どころか` within IPADIC's fused `それどころか` token. Additional rules filter several ambiguous auxiliaries, particles, and nominalizers: for example, auxiliary `う` rather than a character inside a word, passive/potential `れる`, past `た` versus copular `だ`, connective `て` versus case-particle `で`, and hearsay `そう` versus clear appearance/adverbial uses. These checks are implemented in `valid()`.
6. **Count and select examples.** Count each distinct sentence string once per L1 family. Multiple matches within the same sentence still count as one example. Retain the first ten distinct accepted sentences in the novel's reading order; if fewer are found, retain all of them. For overlapping forms within a family, prefer longer spans when highlighting. A sentence can appear under several overlapping L1 families.
7. **Render and record provenance.** Escape source text before inserting HTML, highlight the actual matched spans, and include book, chapter, EPUB member path, paragraph, and sentence-unit references. Include SHA-256 hashes of the input EPUB and XML in the report's source notes. All layout and interaction code is embedded in the HTML. Generation is local and does not use an LLM to write or paraphrase example sentences.

Observed-form counts represent distinct sentence strings containing each form. Literal-L1 counts use the same morphology checks as variant matches. Both are distinct from raw substring occurrence counts.

## Validation and limits

All 2,590 displayed excerpts were checked as exact substrings of the cited EPUB paragraphs after removing ruby annotations. Highlighted spans were checked against the text and against forms registered under the corresponding L1 family. The report was checked for all 341 entries, unique examples within each entry, and exactly `min(10, accepted sentence count)` displayed examples. Browser checks covered search, filters, index navigation, expand/collapse controls, mobile overflow, JavaScript errors, and external network requests.

This is a concordance for study and review. It does not implement Tsutsuji's complete left/right connection constraints, perform dependency parsing, or disambiguate every semantic sense. Some lexical or semantically different uses can remain, and tokenization or dictionary coverage can miss genuine grammar uses. “No match” means none passed these search rules; it does not establish that a construction is absent from the novel. The heuristics were spot-checked, not evaluated against a fully annotated gold-standard corpus.

## Acknowledgments and sources

Thank you to **Haruki Murakami (村上春樹)** for *1Q84*. Its Japanese prose supplies the examples that make this grammar study concrete. Novel excerpts are attributed to the novel and its author; their copyright remains with the respective rights holders.

Thank you to **Suguru Matsuyoshi (松吉俊)**, **Satoshi Sato (佐藤理史)**, and the researchers behind **Tsutsuji (つつじ)** for compiling and sharing a detailed dictionary of Japanese functional expressions and their variants. This analysis depends on that research and on the supplied Tsutsuji 1.1u distribution.

- 松吉俊・佐藤理史・宇津呂武仁 (2007). 「日本語機能表現辞書の編纂」. *自然言語処理*, 14(5), 123–146. [DOI: 10.5715/jnlp.14.5_123](https://doi.org/10.5715/jnlp.14.5_123).
- 松吉俊・佐藤理史 (2008). 「文体と難易度を制御可能な日本語機能表現の言い換え」. *自然言語処理*, 15(2), 75–99. [DOI: 10.5715/jnlp.15.2_75](https://doi.org/10.5715/jnlp.15.2_75).
- The supplied Tsutsuji README credits Suguru Matsuyoshi and Satoshi Sato, © 2008, and specifies [Creative Commons Attribution-ShareAlike 4.0 International](https://creativecommons.org/licenses/by-sa/4.0/). Dictionary-derived expressions and labels retain that attribution and license. Changes here include grouping variants into L1 families, matching them to the supplied novel, adding source references, and presenting the results in HTML. This attribution does not license the novel excerpts under CC BY-SA.
- [Janome](https://github.com/mocobeta/janome) and [lxml](https://lxml.de/) provide Japanese tokenization and XML parsing. Each dependency retains its own license.
