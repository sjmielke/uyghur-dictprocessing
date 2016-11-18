#!/usr/bin/env python3

import argparse
import sys
import codecs
import itertools
import subprocess
import re
import unicodedata
from collections import defaultdict
import spacy
en_nlp = spacy.load('en')

def is_between(x1, c, x2):
  return ord(x1) <= ord(c) <= ord(x2)

def get_strippable_char_set(s):
  def is_messed_up_line(s):
    s = unicodedata.normalize('NFKC', s)
    # Something went very wrong.
    for weirdchar in list("()ª³µ¹º¼ÀÆÉÊËÎÏÐÑÒÔ×àô،") + ['§', '+', '`']:
      if weirdchar in s:
        return True
    # no cyrillic/chinese stuff
    for c in s:
      if is_between('А', c, 'я') or is_between('一', c, chr(99999)):
        return True
    return False
  s = unicodedata.normalize('NFKD', "".join(filter(lambda x: not is_messed_up_line(x), s.splitlines())))
  
  strippables = []
  
  for c in sorted(list(set(s))):
    # A-Za-z0-9 is fine
    if is_between('a', c, 'z') or is_between('A', c, 'Z') or is_between('0', c, '9'):
      continue
    # Arab chars are fine
    if is_between('؀', c, 'ۿ') or c in list("¯"):
      continue
    # Some punctuation is to be expected
    if c in list(" !?.,;-()[]{}|/=:_@\"'~&%\n\t«»—–”“’<>"):
      continue
    # Consciously stripping:
    # - # (that will leave src sep marks |, -<-<, and »»»)
    # - ¡<soft hyphen>
    # - *
    # - all accent marks!
    # - left-to-right marker
    try:
      name = unicodedata.name(c)
    except:
      name = '?'
    print(c + '\t' + str(ord(c)) + '\t' + name)
    
    strippables.append(c)
  return strippables

def apply_until_convergence(f, val):
  while True:
    next_val = f(val)
    if val == next_val:
      break
    else:
      val = next_val
  return val

def strip_parens(s):
  s = apply_until_convergence(lambda v: re.sub(r'\[[^\[]*?\]', '', re.sub(r'\([^(]*?\)', '', v)), s)
  return s

def no_of_upper_chars(s):
  return len(list(filter(lambda c: c.isupper(), s)))

def pick_uppercased(args, l):
  if not args.removelowercased:
    return l
  
  results = []
  for entry1 in l:
    best_entry = entry1
    for entry2 in l:
      if entry1[1].lower() == entry2[1].lower():
        if no_of_upper_chars(entry1[1]) < no_of_upper_chars(entry2[1]):
          best_entry = entry2
        elif no_of_upper_chars(entry1[1]) == no_of_upper_chars(entry2[1]) and entry1[1] != entry2[1]:
          print("Error ", entry1, " == ", entry2, file = sys.stderr)
    results.append(best_entry)
  return results

def cleanabbrevs(s):
  return re.sub(r'([^\w]|^)th\. ' , "\\1the ",\
         re.sub(r'([^\w]|^)esp\. ', "\\1especially ",\
         re.sub(r'([^\w]|^)sb\.'  , "\\1somebody",\
         re.sub(r'([^\w]|^)smb\.' , "\\1somebody",\
         re.sub(r'([^\w]|^)sth\.' , "\\1something",\
         re.sub(r'([^\w]|^)smth\.', "\\1something",\
         s))))))

def spacysplit(in_trg):
  results = []
  trg = in_trg.strip()
  if trg == '':
    return trg
  
  # Spacy really chokes on non-ascii chars, which is bad in "see XYZBLA BLUBB"
  if len(trg) > 3 and trg[0:4] == 'see ' and not len(trg) == len(trg.encode()):
    real_sentences = [trg]
  else:
    # Recursive split for sentences, spacy isn't idempotent...
    def gimme_all_sents(s):
      s = s.strip()
      
      # Or don't, if thats better
      sents = [str(se) for se in list(en_nlp(s).sents)]
      
      # Add a dot to make sure the last thing will be it's own sentence, if that's better
      sents_dot = [str(se) for se in list(en_nlp(s + '.').sents)]
      if len(sents_dot) > len(sents):
        sents = sents_dot
        sents[-1] = sents[-1][:-1]
        if sents[-1] == '':
          sents = sents[:-1]
      
      # Or remove last punctuation, if it's possible and helps!
      if len(s) > 1 and s[-1] in ['.', '!', '?']:
        removed_dot = s[-1]
        sents_antidot = [str(se) for se in list(en_nlp(s[:-1]).sents)]
        if len(sents_antidot) > len(sents):
          sents = sents_antidot
          sents[-1] = sents[-1] + removed_dot
      
      # Stop recursion
      if len(sents) == 1:
        return [str(s)]
      
      # Recurse at will!
      results = []
      for sent in sents:
        results += gimme_all_sents(sent)
      
      #print(str(s), ' ~> ', results)
      
      return results
    
    # Sadly, spacy oversplits at the dash
    real_sentences = []
    for spacy_sentence in gimme_all_sents(trg):
      if real_sentences != [] and real_sentences[-1][-1] in ['–', '\'']:
        real_sentences[-1] = real_sentences[-1] + ' ' + str(spacy_sentence)
      else:
        real_sentences.append(str(spacy_sentence))
  
  # Now we have proper sentences
  for sentence in real_sentences:
    # Remove "..." and "word." and trim
    clipped_sent = re.sub(r'\.\.+', '', \
                   re.sub(r'([^\.A-Z])\.$','\\1', \
                   str(sentence))).strip()
    # If theres anything useful left, okay!
    if clipped_sent.replace('.','') != "":
      results.append(clipped_sent)
  return results

def main():
  parser = argparse.ArgumentParser(description="Given LRLP lexicon flat representation attempt to normalize it to short phrase form",
                                   formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument("--infile", "-i", nargs='?', type=argparse.FileType('r'), default=sys.stdin, help="input lexicon file")
  parser.add_argument("--outfile", "-o", nargs='?', type=argparse.FileType('w'), default=sys.stdout, help="output instruction file")
  parser.add_argument("--explainfile", "-e", nargs='?', type=argparse.FileType('w'), default=None, help="explanation output file")
  parser.add_argument("--nosplit", "-n", action='store_true', default=False, help="don't split target on commas/semicolons/or/slash")
  parser.add_argument("--targetlimit", "-l", type=int, default=4, help="maximum length of target entry after splitting")
  parser.add_argument("--earlytargetlimit", "-L", type=int, default=20, help="maximum length of target entry (number of words) before splitting")
  parser.add_argument("--singletons", "-s", action='store_true', default=False, help="only split src/trg pairs")
  parser.add_argument("--removelowercased", action='store_true', default=False, help="remove lowercased variants of uppercased translations")
  parser.add_argument("--nospacysplit", action='store_true', default=False, help="don't split targets using spacy.io parser")

  try:
    args = parser.parse_args()
  except IOError as msg:
    parser.error(str(msg))

  outfile = args.outfile
  stderr = sys.stderr

  infile = args.infile.read()
  strippables = get_strippable_char_set(infile)
  
  originaldict = defaultdict(list)
  cleaneddict = defaultdict(list)
  resultdict = defaultdict(list)
  bad = 0
  toomanywords = 0
  wrote = 0
  for line in infile.splitlines():
    # Do global cleanup
    line = "".join(filter(lambda c: c not in strippables, unicodedata.normalize('NFKD', line.replace('ı', 'i'))))
    
    try:
      srcs, origin, trgs = line.strip().split("\t")
      originaldict[srcs].append((origin, trgs))
    except:
      bad += 1
      continue
    if len(trgs.split()) > args.earlytargetlimit:
      toomanywords += 1
      continue
    
    # clean up source side
    srcs = strip_parens(srcs)
    # normalize whitespace
    srcs = " ".join(srcs.split())
    # now split
    srcs = [srcs] if args.nosplit else re.split(r'[;,/،]|-<-<|\||»+| or |. [0-9]+', srcs)
    
    # clean up target side
    trgs = strip_parens(trgs)
    trgs = re.sub(r'e\.g\..*', '', trgs) # e.g. comes before garbage
    trgs = re.sub(r'«[A-Z]+»', '', trgs) # strip categories like «BOT»
    trgs = trgs.replace("«MEC]", "").replace("«TEX]", "").replace("«СINE»", "") # a few unclean ones
    # normalize whitespace
    trgs = " ".join(trgs.split())
    # clean sth. -> something
    trgs = cleanabbrevs(trgs)
    # delete full stop at end
    #trgs = trgs[0:-1] if len(trgs) > 0 and trgs[-1] == '.' else trgs
    
    # split on commas, semicolons, "or" and sense disambiguations/ends on target side
    trgs = [trgs] if args.nosplit else re.split(r'[;,/،]|-<-<|\||»+| or |. [0-9]+', trgs)
    
    for src in srcs:
      src = src.strip()
      
      for coarse_trg in trgs:
        # filter unsure entries
        if "??" in coarse_trg or "\"" in coarse_trg:
          continue
        # Otherwise do spacy.io's fine splitting
        fine_targets = spacysplit(coarse_trg.strip()) if not args.nospacysplit else [coarse_trg.strip()]
        for trg in fine_targets:
          # Only strip actual infinitives, not prepositions!
          if len(trg) > 3 and trg[3].islower():
            trg = re.sub(r'^to ', '', trg)
          trg = re.sub(r'^be ', '', trg)
          trg = re.sub(r'^NO_GLOSS$', '', trg)
          trg = re.sub(r'^dial> ', '', trg)
          trg = trg.strip()
          
          # cleaned out all junk?
          if len(trg) == 0 or len(src) == 0:
            continue
          # nothing too long
          if len(trg.split()) > args.targetlimit:
            toomanywords += 1
            continue
          
          # Now NFKC again
          src = unicodedata.normalize('NFKC', src)
          origin = unicodedata.normalize('NFKC', origin)
          trg = unicodedata.normalize('NFKC', trg)
          cleaneddict[src].append((origin, trg))
  
  def is_arab_char(c):
    return ord(c) >= 1536 and ord(c) <= 1791
  def is_weird_char(c):
    return is_arab_char(c) or not c.isalpha()
  
  # Resolve all mentions!
  def trans_through(word: str, path: [str] = []) -> [(str, str)]:
    # Stop recursion
    if word in path:
      return []
    
    # Check for mentions
    res = []
    for (origin, t) in cleaneddict[word]:
      next_word = re.sub('^see|^form of|^[a-z]+ form of', '', t)
      if next_word != t: # we did find a match
        next_word = "".join(itertools.takewhile(is_weird_char, next_word)).strip()
        if next_word != "":
          # We found a match so let's resolve that instead of appending
          res += trans_through(next_word, path + [word])
          continue
      res.append((origin, t))
    return res
  
  for src in list(cleaneddict.keys()):
    uppercaseds = pick_uppercased(args, set(trans_through(src)))
    translations = sorted(list(set(uppercaseds)))
    # Singletons or "normal" entries?
    if not args.singletons:
      resultdict[src] = translations
    else:
      allsrcs = src.split()
      if len(allsrcs) > 1:
        for (origin, trg) in translations:
          alltrgs = trg.split()
          if len(allsrcs) == len(alltrgs):
            for (singleton_src, singleton_trg) in zip(allsrcs, alltrgs):
              if all(map(is_arab_char, singleton_src)) and (origin, singleton_trg) not in cleaneddict[singleton_src]: # 25255
                resultdict[singleton_src].append((origin, singleton_trg))
  
  for src in sorted(list(resultdict.keys())):
    for (origin, trg) in sorted(resultdict[src]):
      outfile.write("%s\t%s\t%s\n" % (src, origin, trg))
      wrote += 1
  
  if args.explainfile != None:
    # Now print what we did!
    all_sources = sorted(list(set(list(resultdict.keys()) + list(originaldict.keys()))))
    
    # First romanize all sources.
    #romanized, _ = subprocess.Popen("/home/sjm/documents/ISI/uroman-v0.5/bin/uroman.pl", stdin=subprocess.PIPE, stdout=subprocess.PIPE).communicate("\n".join(all_sources).encode('utf-8'))
    #romanized_sources = romanized.decode('utf-8').splitlines().reversed()
    
    for src in all_sources:
      print("»{}«".format(src), file = args.explainfile)
      print("(original)", file = args.explainfile)
      for (origin, t) in sorted(originaldict[src]):
        print("  " + t, file = args.explainfile)
      print("(result)", file = args.explainfile)
      for (origin, t) in sorted(resultdict[src]):
        print("  " + t, file = args.explainfile)
      print("", file = args.explainfile)
    
    #assert romanized_sources == []
    assert len(sorted(list(resultdict.keys()))) == len(set(sorted(list(resultdict.keys()))))
    for src in sorted(list(resultdict.keys())):
      assert len(resultdict[src]) == len(set(resultdict[src]))
  
  stderr.write("%d bad %d too many target words %d wrote\n" % (bad, toomanywords, wrote))

if __name__ == '__main__':
  main()

