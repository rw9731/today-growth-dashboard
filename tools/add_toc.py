"""Insert the floating TOC (tools/toc_snippet.html) into pages and templates that don't have one (Reina 11/9：所有页面都要有目录).

Usage:
  python3 tools/add_toc.py <file> [<file> ...]

Puts the snippet right before </body>. Files that already have it (id="gtoc") get the current version swapped in.
Daily pages and tools/template.html have their own TOC (id="toc") and are skipped.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SNIP = open(os.path.join(HERE, 'toc_snippet.html'), encoding='utf-8').read().strip()
PAT = re.compile(r'<!-- 悬浮目录（Reina 11/9.*?</script>', re.S)


def main():
    for p in sys.argv[1:]:
        s = open(p, encoding='utf-8').read()
        if 'id="toc"' in s:
            print('skip (has daily toc)', p)
            continue
        if 'id="gtoc"' in s:
            s2 = PAT.sub(lambda m: SNIP, s, count=1)
        else:
            i = s.rfind('</body>')
            if i < 0:
                print('skip (no </body>)', p)
                continue
            s2 = s[:i] + SNIP + '\n' + s[i:]
        if s2 != s:
            open(p, 'w', encoding='utf-8').write(s2)
            print('ok', p)


if __name__ == '__main__':
    main()
