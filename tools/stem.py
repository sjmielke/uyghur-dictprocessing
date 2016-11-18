import re
import sys
import argparse

parser = argparse.ArgumentParser(description="Pivot two dicts on english output",
                                  formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("grammarfile", type=argparse.FileType('r'))
parser.add_argument("lexicon")

try:
  args = parser.parse_args()
except IOError as msg:
  parser.error(str(msg))

noun_regexes = []
verb_regexes = []
for line in args.grammarfile.read().splitlines():
  if "stemming" not in line:
    continue
  r1, r2, cat = re.search(r'::uig /(.*)/(.*)/ ::synt lexical (noun|verb) stemming', line).groups()
  if cat == "noun":
    noun_regexes.append((re.compile(r1), r2.replace('$', "\\")))
  elif cat == "verb":
    verb_regexes.append((re.compile(r1), r2.replace('$', "\\")))
  else:
    print("Unknown category:", cat, file = sys.stderr)

print("Noun regexes", file = sys.stderr)
for (r1, r2) in noun_regexes:
  print(r1, "->", r2, file = sys.stderr)
print("Verb regexes", file = sys.stderr)
for (r1, r2) in verb_regexes:
  print(r1, "->", r2, file = sys.stderr)


with open(args.lexicon                               ) as lexfile,\
     open(args.lexicon              + ".postags"     ) as postagfile,\
     open(args.lexicon + ".stemmed"             , 'w') as lexfile_out,\
     open(args.lexicon + ".stemmed" + ".postags", 'w') as postagfile_out:
  for (lexentry, postag) in zip(lexfile.read().splitlines(), postagfile.read().splitlines()):
    src, origin, trg = lexentry.strip().split("\t")
    
    regexes = []
    if postag == 'NOUN':
      regexes = noun_regexes
    if postag == 'VERB':
      regexes = verb_regexes
    
    for (pat, rep) in regexes:
      newsrc = pat.sub(rep, src)
      if src != newsrc:
        print("{}\t{}\t{}".format(newsrc, origin, trg), file = lexfile_out)
        print(postag, file = postagfile_out)
