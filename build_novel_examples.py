"""Build an offline L1 concordance from the user-supplied EPUB."""
from __future__ import annotations

import argparse
from collections import Counter, deque
from hashlib import sha256
import html
import json
from pathlib import Path
import re
from urllib.parse import unquote
from zipfile import ZipFile

from lxml import etree as ET

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'outputs' / '1q84-l1'
EPUB = ROOT / '1Q84 (全三冊).epub'
XML = ROOT / 'tsutsuji1.1.xml'
TEMPLATE = ROOT / 'novel_report_template.html'


def local(node):
    return ET.QName(node).localname


def entries():
    result = []
    for node in ET.parse(str(XML)).getroot():
        entry = {'id': node.get('L1ID'), 'expression': node.get('BASE').replace('.', ''),
                 'meanings': sorted({n.get('MEANING') for n in node if n.get('MEANING')}),
                 'forms': set(), 'examples': [], 'total': 0, 'literal_total': 0,
                 'form_counts': Counter(), '_seen': set()}
        for child in node.iter():
            if local(child) == 'L9':
                entry['forms'].add((child.text or '').strip().replace('.', ''))
        entry['forms'].add(entry['expression'])
        result.append(entry)
    return sorted(result, key=lambda e: (e['expression'], e['id']))


def sentences(text):
    """Split dialogue too, but retain a closing quote's attached reporting clause."""
    start, i = 0, 0
    while i < len(text):
        ch = text[i]
        if ch in '。！？!?':
            end = i + 1
            while end < len(text) and text[end] in '。！？!?」』）)]':
                end += 1
            closing_quote = any(c in '」』' for c in text[i+1:end])
            if closing_quote and re.match(r'(?:と|って|など|、|を|は)', text[end:].lstrip()):
                i = end
                continue
            if text[start:end].strip():
                yield start, end, text[start:end].strip()
            start, i = end, end
        else:
            i += 1
    if text[start:].strip():
        yield start, len(text), text[start:].strip()


def corpus():
    ns = {'n': 'http://www.daisy.org/z3986/2005/ncx/'}
    rows, chapters = [], []
    with ZipFile(EPUB) as z:
        toc = ET.fromstring(z.read('toc.ncx'))
        for nav in toc.findall('.//n:navPoint', ns):
            label = nav.findtext('n:navLabel/n:text', namespaces=ns) or ''
            if not re.search(r'第.{1,4}章', label):
                continue
            path = unquote(nav.find('n:content', ns).get('src').split('#')[0])
            doc = ET.fromstring(z.read(path))
            book = ''.join(doc.xpath('//*[local-name()="title"]/text()')).strip()
            ps = doc.xpath('//*[local-name()="body"]//*[local-name()="p"]')
            for rt in list(doc.xpath('//*[local-name()="rt" or local-name()="rp"]')):
                # Preserve text after the ruby annotation.
                parent, tail = rt.getparent(), rt.tail
                previous = rt.getprevious()
                if tail:
                    if previous is not None:
                        previous.tail = (previous.tail or '') + tail
                    else:
                        parent.text = (parent.text or '') + tail
                parent.remove(rt)
            nonblank = 0
            chapter_sentences = 0
            for pnum, p in enumerate(ps, 1):
                text = ''.join(p.itertext()).strip()
                if not text:
                    continue
                nonblank += 1
                # In this EPUB, the first two nonblank paragraphs are heading/subtitle.
                if nonblank <= 2:
                    continue
                for snum, (begin, end, sentence) in enumerate(sentences(text), 1):
                    if not sentence:
                        continue
                    rows.append({'text': sentence, 'book': book, 'chapter': label,
                                 'source': path, 'paragraph': pnum, 'sentence': snum})
                    chapter_sentences += 1
            chapters.append({'book': book, 'chapter': label, 'source': path,
                             'sentences': chapter_sentences})
    assert len(chapters) == 79, len(chapters)
    assert all(c['sentences'] > 0 for c in chapters)
    return rows, chapters


class Matcher:
    """Aho–Corasick search for all dictionary forms in one pass per sentence."""
    def __init__(self, forms):
        self.go, self.fail, self.output = [{}], [0], [[]]
        for form, owners in forms.items():
            at = 0
            for char in form:
                if char not in self.go[at]:
                    self.go[at][char] = len(self.go)
                    self.go.append({}); self.fail.append(0); self.output.append([])
                at = self.go[at][char]
            self.output[at].append((form, owners))
        q = deque(self.go[0].values())
        while q:
            at = q.popleft()
            for char, child in self.go[at].items():
                q.append(child)
                f = self.fail[at]
                while f and char not in self.go[f]:
                    f = self.fail[f]
                self.fail[child] = self.go[f].get(char, 0)
                self.output[child].extend(self.output[self.fail[child]])

    def find(self, text):
        at = 0
        for end, char in enumerate(text, 1):
            while at and char not in self.go[at]:
                at = self.fail[at]
            at = self.go[at].get(char, 0)
            for form, owners in self.output[at]:
                yield end - len(form), end, form, owners


def valid(root, form, tokens, first, last):
    """Conservative POS checks for short and highly ambiguous forms."""
    t = tokens[first]
    pos, base = t.part_of_speech.split(','), t.base_form
    last_t = tokens[last]
    if root == '326':
        return pos[0] == '助動詞' and base == 'う'
    if root == '332':
        return (pos[0] == '助動詞' or pos[:2] == ['動詞', '接尾']) and base in {'れる', 'られる'}
    if root == '328':
        return pos[0] == '助動詞' and base == 'たい'
    if root == '334':
        return pos[0] == '助動詞' and base == 'ない'
    if root == '335':
        return pos[0] == '助動詞' and base in {'ぬ', 'ん', 'ず'}
    if root == '338':
        # IPADIC labels the voiced past auxiliary だ with base だ too.
        if pos[0] != '助動詞':
            return False
        if form.startswith('た'):
            return base == 'た'
        return first > 0 and tokens[first-1].part_of_speech.startswith('動詞') and tokens[first-1].infl_form == '連用タ接続'
    if root == '320':
        if form == 'じゃ':
            return pos[0] == '助詞' or (pos[0] == '助動詞' and base == 'だ')
        if not (pos[0] == '助動詞' and base in {'だ', 'です'}):
            return False
        if form.startswith('だ') and first > 0 and tokens[first-1].part_of_speech.startswith('動詞') and tokens[first-1].infl_form == '連用タ接続':
            return False
        return True
    if root == '337':
        return pos[:2] == ['助詞', '接続助詞']
    if root == '034':
        return pos[:2] == ['助詞', '格助詞']
    if root in {'315', '316', '317'}:
        return pos[:2] == ['助詞', '終助詞']
    if root in {'293', '294', '297', '298', '299', '095', '247', '059', '057'}:
        return pos[0] == '助詞'
    if root == '336':
        # Tsutsuji そう is hearsay: it follows a complete predicate.
        # Reject appearance uses such as 不思議そう and 誇らしそう.
        if '助動詞語幹' not in pos:
            return False
        if first == 0:
            return False
        previous = tokens[first-1]
        if previous.base_form == 'だ' and first > 1 and tokens[first-2].base_form == 'そう':
            return False  # Repetition: そうだそうだ (agreement), not reported information.
        return previous.part_of_speech.split(',')[0] in {'動詞', '形容詞', '助動詞'} and previous.infl_form in {'基本形', '文語基本形', '連体形'}
    if root == '324':
        return pos[0] == '名詞' and '助動詞語幹' in pos
    if root == '159' and form == 'こと':
        return pos[0] == '名詞' and pos[1] == '非自立'
    if root == '082' and form == 'もの':
        return pos[0] == '名詞' and pos[1] == '非自立'
    if root == '161' and form == 'の':
        # Exclude ordinary possessive/attributive の, absent from this L1's senses.
        return pos[0] == '助詞' and pos[1] != '連体化' or pos[:2] == ['名詞', '非自立']
    return True


def analyze():
    from janome.tokenizer import Tokenizer
    es = entries()
    rows, chapters = corpus()
    forms = {}
    for i, e in enumerate(es):
        for form in e['forms']:
            forms.setdefault(form, []).append(i)
    matcher = Matcher(forms)
    tokenizer = Tokenizer()
    print(f'Extracted {len(rows):,} sentence units from {len(chapters)} chapters; searching {len(forms):,} distinct forms.', flush=True)
    for num, row in enumerate(rows, 1):
        text = row['text']
        hits = list(matcher.find(text))
        if not hits:
            continue
        tokens = list(tokenizer.tokenize(text))
        starts, ends, offset = {}, {}, 0
        for ti, token in enumerate(tokens):
            # Janome may skip whitespace: locate each token in the untouched source.
            at = text.find(token.surface, offset)
            assert at >= offset, (num, token.surface)
            starts[at], ends[at+len(token.surface)] = ti, ti
            # IPADIC fuses the demonstrative with this grammatical connector.
            if token.surface == 'それどころか':
                starts[at+2] = ti
            offset = at+len(token.surface)
        by_entry = {}
        for start, end, form, owners in hits:
            if start not in starts or end not in ends:
                continue
            for owner in owners:
                if valid(es[owner]['id'], form, tokens, starts[start], ends[end]):
                    by_entry.setdefault(owner, []).append((start, end, form))
        for owner, matches in by_entry.items():
            e = es[owner]
            if text in e['_seen']:
                continue
            e['_seen'].add(text)
            e['total'] += 1
            if any(form == e['expression'] for _, _, form in matches):
                e['literal_total'] += 1
            for form in {m[2] for m in matches}:
                e['form_counts'][form] += 1
            if len(e['examples']) < 10:
                # Prefer the longest overlapping form when highlighting a family.
                selected = []
                for match in sorted(set(matches), key=lambda m: (-(m[1]-m[0]), m[0], m[2])):
                    if not any(match[0] < old[1] and old[0] < match[1] for old in selected):
                        selected.append(match)
                e['examples'].append(dict(row, matches=sorted(selected)))
        if num % 5000 == 0:
            print(f'Processed {num:,}/{len(rows):,} sentence units', flush=True)
    for e in es:
        del e['_seen']
        e['forms'] = sorted(e['forms'])
        e['form_counts'] = dict(sorted(e['form_counts'].items(), key=lambda item: (-item[1], item[0])))
    data = {'entries': es, 'chapters': chapters, 'sentences': len(rows),
            'source': EPUB.name, 'epub_sha256': sha256(EPUB.read_bytes()).hexdigest(),
            'dictionary_sha256': sha256(XML.read_bytes()).hexdigest(),
            'tokenizer': 'Janome 0.5.2 / bundled IPADIC',
            'sentence_policy': 'Japanese terminal punctuation, including inside dialogue; a final quoted sentence stays with an attached reporting clause; original quote marks and final unpunctuated paragraph fragments retained.'}
    (OUT / 'matches.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return data


def highlight(text, matches):
    parts, at = [], 0
    for begin, end, form in matches:
        assert text[begin:end] == form
        parts += [html.escape(text[at:begin]), '<mark>'+html.escape(text[begin:end])+'</mark>']
        at = end
    return ''.join(parts)+html.escape(text[at:])


def render(data):
    es = data['entries']
    found = sum(e['total'] > 0 for e in es)
    ten = sum(e['total'] >= 10 for e in es)
    count = sum(len(e['examples']) for e in es)
    cards, links = [], []
    for e in es:
        ident, title = e['id'], html.escape(e['expression'])
        status = 'full' if e['total'] >= 10 else 'partial' if e['total'] else 'none'
        examples = []
        for x in e['examples']:
            forms = '、'.join(dict.fromkeys(m[2] for m in x['matches']))
            literal = any(m[2] == e['expression'] for m in x['matches'])
            examples.append(f'<li><p class="sentence" lang="ja">{highlight(x["text"], x["matches"])}</p>'
                            f'<div class="citation">{html.escape(x["book"])} · {html.escape(x["chapter"])}'
                            f' · paragraph {x["paragraph"]}, sentence unit {x["sentence"]}'
                            f'<span class="source-file">{html.escape(x["source"])}</span></div>'
                            f'<div class="match-label">{"L1 form" if literal else "Dictionary variant"}: <span lang="ja">{html.escape(forms)}</span></div></li>')
        meanings = html.escape(' / '.join(e['meanings']))
        top = '、'.join(list(e['form_counts'])[:12])
        meta = f'<p class="entry-meta">Source meaning labels: <span lang="ja">{meanings}</span></p>'
        meta += f'<p class="entry-meta">Searched {len(e["forms"]):,} forms · {e["literal_total"]:,} sentence units match the literal L1 spelling.</p>'
        if top:
            meta += '<p class="entry-meta">Observed forms: <span lang="ja">'+html.escape(top)+'</span></p>'
        body = '<ol>'+''.join(examples)+'</ol>' if examples else '<p class="empty">No matching sentence found under these dictionary and morphology rules.</p>'
        shown = len(examples)
        cards.append(f'<details class="entry" id="g-{ident}" data-status="{status}" data-name="{title}" data-id="{ident}">'
                     f'<summary><span class="entry-title" lang="ja">{title}</span><span class="entry-id">L1 {ident}</span>'
                     f'<span class="badge {status}">{shown}/10 examples</span><span class="total">{e["total"]:,} matching sentence units</span></summary>'
                     f'<div class="entry-body">{meta}{body}</div></details>')
        links.append(f'<a href="#g-{ident}" data-target="g-{ident}"><span lang="ja">{title}</span><small>{ident} · {shown}/10</small></a>')
    template = TEMPLATE.read_text(encoding='utf-8')
    replacements = {'__FOUND__':str(found), '__TEN__':str(ten), '__NONE__':str(len(es)-found),
                    '__EXAMPLES__':f'{count:,}', '__SENTENCES__':f'{data["sentences"]:,}',
                    '__CARDS__':''.join(cards), '__LINKS__':''.join(links),
                    '__EPUB_SHA__':data['epub_sha256'], '__DICT_SHA__':data['dictionary_sha256']}
    for key, value in replacements.items():
        template = template.replace(key, value)
    target = OUT / '1Q84_L1_grammar_examples.html'
    target.write_text(template, encoding='utf-8')
    assert len(es) == 341
    assert all(len(e['examples']) == min(10, e['total']) for e in es)
    assert all(len({x['text'] for x in e['examples']}) == len(e['examples']) for e in es)
    print(json.dumps({'entries':len(es), 'with_examples':found, 'with_ten':ten,
                      'with_1_to_9':found-ten, 'no_match':len(es)-found,
                      'examples':count, 'html_bytes':target.stat().st_size}, indent=2), flush=True)
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--epub', type=Path, default=EPUB, help='Local 1Q84 EPUB (not included)')
    parser.add_argument('--dictionary', type=Path, default=XML, help='Local Tsutsuji 1.1u XML (not included)')
    parser.add_argument('--output-dir', type=Path, default=OUT, help='Directory for the HTML and intermediate matches.json')
    parser.add_argument('--template', type=Path, default=TEMPLATE, help='HTML template used to render the report')
    parser.add_argument('--render-only', action='store_true', help='Render existing matches.json without reading source data')
    args = parser.parse_args()
    EPUB, XML = args.epub.expanduser().resolve(), args.dictionary.expanduser().resolve()
    OUT, TEMPLATE = args.output_dir.expanduser().resolve(), args.template.expanduser().resolve()
    required = [TEMPLATE, OUT/'matches.json'] if args.render_only else [TEMPLATE, EPUB, XML]
    for path in required:
        if not path.is_file():
            parser.error(f'Required file not found: {path}')
    OUT.mkdir(parents=True, exist_ok=True)
    data = json.loads((OUT/'matches.json').read_text()) if args.render_only else analyze()
    print(render(data))
