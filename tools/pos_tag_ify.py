import sys
import spacy
en_nlp = spacy.load('en')

for line in sys.stdin.read().splitlines():
  doc = en_nlp(line)
  postag = 'UNK'
  for tok in doc:
    #print("{!s:<10} {!s:<6} {}".format(tok, tok.pos_, "(head)" if tok.head == tok else ""))
    if tok.head == tok:
      postag = tok.pos_
      break
  print(postag)
