# dictionaryCLI

Look up words in the Cambridge Dictionary straight from your terminal - definitions,
IPA pronunciations, example sentences, offline access, pronunciation audio, and your
own vocabulary wordlists.

```
  apple  /ˈæp.əl/ UK  /ˈæp.əl/ US
───────────────────────────────────────────────────────────────────────────────
noun [ C or U ]
  [A1] a round fruit with firm, white flesh and a green, red, or yellow skin
       • to peel an apple
       • apple pie
       • an apple tree
```

## Features

- **Lookup** - definitions, UK/US IPA, grammar codes, CEFR levels (A1-C2), usage labels,
  guidewords, and example sentences, rendered with colors
- **Search** - website-style dropdown matches (`dict search photogr`), pick by arrow keys
  or `-pN`
- **Interactive mode** - a REPL for continuous lookups without re-launching
- **Offline cache** *(opt-in)* - save every word you look up and read them with no
  internet; background prefetching of related words while you browse
- **Wordlists** - star words, browse them in an arrow-key picker, export/import as plain
  text
- **Audio** - play real Cambridge UK/US pronunciations

Works on Windows, macOS, and Linux.

## Install

With [pipx](https://pipx.pypa.io/) (recommended):

```
pipx install git+https://github.com/HarvyLiu/dictionaryCLI.git
```

Or from a local clone:

```
git clone https://github.com/HarvyLiu/dictionaryCLI.git
cd dictionaryCLI
pipx install .
```

No pipx? A plain virtualenv works too:

```
cd dictionaryCLI
py -m venv .venv
.venv\Scripts\activate          # Windows  (source .venv/bin/activate on Unix)
pip install .
```

## Usage

| Command | What it does |
| --- | --- |
| `dict apple` | look up a word or phrase |
| `dict apple --audio` | look up and play UK pronunciation (`--audio us` for US) |
| `dict search photogr` | show matching words like the website dropdown |
| `dict search photogr -p3` | look up the 3rd match directly |
| `dict add serendipity` | star a word and always keep an offline copy |
| `dict remove apple` | unstar a word (alias: `rm`) |
| `dict list` | arrow-key browser for starred words; Enter looks one up |
| `dict list --plain` | plain-text listing instead of the picker |
| `dict export my-words.txt` | write your wordlist as plain text |
| `dict import my-words.txt` | star every word in a text file (`--no-fetch` to skip downloads) |
| `dict cache on/off/status/list/clear` | manage the offline cache |
| `dict` | interactive mode |

### Interactive mode

Run `dict` with no arguments:

```
Cambridge Dictionary CLI - type a word, :s <query> search, :w browse list,
:a add last, :v audio, :rm, :q quit | cache: OFF
dict>
```

| Shortcut | Action |
| --- | --- |
| `<word>` | look up |
| `:s <query>` | search with candidates |
| `:w` | open the wordlist picker |
| `:a` | star the last word you looked up |
| `:v [word]` | play pronunciation |
| `:rm [word]` | unstar |
| `:cache on/off/status` | toggle caching mid-session |
| `:q`, Ctrl+C | quit |

## Offline cache

Caching is **opt-in and off by default** - nothing is written to disk until you ask for
it:

```
dict cache on        start saving every lookup (~1 KB per word)
dict cache off       stop saving; saved words are kept
dict cache status    where data lives and how much space it uses
dict cache clear     delete all saved words
```

While caching is on you can still look up saved words with no internet - they render
with an `[offline - showing saved copy]` badge. Starred words (`dict add`) are always
cached, even with the global cache off.

Data lives in your platform data folder, e.g. `%LOCALAPPDATA%\dictcli\` on Windows,
`~/.local/share/dictcli/` on Linux.

## Wordlist files

Export/import format is deliberately boring - one word per line, `#` comments allowed:

```
# exam prep
serendipity
give up
run away
```

That makes lists easy to edit, sync, and share.

## Development

```
git clone https://github.com/HarvyLiu/dictionaryCLI.git
cd dictionaryCLI
py -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

Tests use recorded HTML fixtures - no network needed.

## Disclaimer

This is an unofficial client that parses public web pages for personal use. All
dictionary content is © Cambridge University Press & Assessment - please be reasonable
with request volume.

## License

[MIT](LICENSE)
