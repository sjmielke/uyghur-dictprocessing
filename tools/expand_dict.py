import re
import sys
import itertools

def interpret_grammar(grammarfilename, pertainymfilename):
	noun_adjective_dict = {}
	
	with open(pertainymfilename) as pertainymfile:
		for line in pertainymfile.read().splitlines():
			match = re.search(r'^::s-(adj|noun) (.*) ::t-(adj|noun) (.*)$', line)
			if match == None:
				continue
			cat1, w1, cat2, w2 = match.groups()
			if cat1 == "adj" and cat2 == "noun":
				tmp = w1
				w1 = w2
				w2 = tmp
			noun_adjective_dict[w1.strip()] = w2.strip()

	# grep '::synt noun suffix' grammar.uig-v02.txt | grep ::eng | sed 's/ ::synt noun suffix ::function /	/;s/	.*::eng /	/;s/::uig //;s/ ::.*$//'

	adjectivizers, prefixers, suffixers = [], [], []
	
	with open(grammarfilename) as grammarfile:
		for line in grammarfile.read().splitlines():
			if "::synt noun suffix" in line:
				uig = re.search(r'::uig ([^:]*) ::', line).group(1)
				if "adjectivizer" in line:
					adjectivizers.append(uig)
				elif "::eng" in line:
					all_eng = re.search(r'::eng ([^:]*)', line).group(1).strip()
					eng_alternatives = all_eng.split(';')
					for raweng in eng_alternatives:
						eng = re.sub(r'\([^\(\)]+\)', '', raweng).strip()
						eng_words = eng.split()
						newphrases = [""]
						for word in eng_words:
							if '/' in word:
								choices = word.split('/')
								newnewphrases = []
								for choice in choices:
									newnewphrases.append(list(map(lambda p: p + ' ' + choice, newphrases)))
								newphrases = itertools.chain(*newnewphrases)
							else:
								newphrases = list(map(lambda p: p + ' ' + word, newphrases))
						for eng in newphrases:
							eng = eng[1:]
							if eng[0] == "'":
								suffixers.append((uig, ' ' + eng))
							elif eng[0] == "-":
								suffixers.append((uig, eng[1:]))
							else:
								prefixers.append((uig, eng + ' '))

	return (adjectivizers, prefixers, suffixers, noun_adjective_dict)



if __name__ == '__main__':
	adjectivizers, prefixers, suffixers, noun_adjective_dict = interpret_grammar(sys.argv[1], sys.argv[2])
	for line in sys.stdin.read().splitlines():
		print(line)
		src, cat, trg = line.split('\t')
		for srcsuf in adjectivizers:
			adj = noun_adjective_dict[trg] if trg in noun_adjective_dict else trg
			print(src + srcsuf + '\t' + cat + '\t' + adj)
		for (srcsuf, trgpre) in prefixers:
			if cat == "PER" and re.match(r'.*\b(in|on)\b.*', trgpre):
				continue
			print(src + srcsuf + '\t' + cat + '\t' + trgpre + trg)
		for (srcsuf, trgsuf) in suffixers:
			print(src + srcsuf + '\t' + cat + '\t' + trg + trgsuf)
