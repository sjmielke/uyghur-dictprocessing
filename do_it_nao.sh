OUTDIR=v15

mkdir -p $OUTDIR
rm -f $OUTDIR/*

# Make sure the input file has 3 columns src/UNK/trg, add the middle one, if necessary
# Also NFKC everything and delete \x03.
threecol ()
{
	f=$1
	( if [[ $(awk -F $'\t' '{print NF}' $f | sort | tail -n 1) -eq 2 ]]; then
		sed 's/	/	UNK	/' $f
	else
		cat $f
	fi ) | python3 -c "import sys; import unicodedata; print(unicodedata.normalize('NFKC', sys.stdin.read().replace('\x03', '')), end='');"
}

# Generates POS-tag file for trg side of some dict file
pos-tag-ify()
{
	f=$1
	cut -f 3 $f | python3 tools/pos_tag_ify.py > $f.postags
}

# Reverses a trg/UNK/src dict so src/UNK/trg
flip-dict ()
{
	dict=$1
	for col in 1 2 3; do
		cut -f $col $dict > $dict.flip$col
	done
	paste $dict.flip{3,2,1} > $dict
	rm $dict.flip{1,2,3}
}

# Wrapper around normalize script, generating both non-singleton and singleton version
norm-dict ()
{
	d=$1
	python3 tools/norm_flat_uyghur_dict.py $2 $3 $4    --infile $d --outfile $d.norm
	python3 tools/norm_flat_uyghur_dict.py $2 $3 $4 -s --infile $d --outfile $d.norm.singletons
}

# Sorts a dict file - while also sorting the POS-tag file accordingly!
sort-safely()
{
	f=$1
	if [ ! "${f##*.}" = "postags" ]; then
		if [ -s "$f.postags" ]; then
			tmpfile=$(mktemp)
			paste $f $f.postags | \
				LC_COLLATE='UTF-8' sort -u \
				> $tmpfile
			cut -f 1-3 $tmpfile > $f
			cut -f 4   $tmpfile > $f.postags
			rm $tmpfile
		else
			LC_COLLATE='UTF-8' sort -u -o $f $f
		fi
	fi
}


echo -n "" > $OUTDIR/all_lexicons

echo "Now processing dictionaries"

# Simple dicts
for dict in ldc-lexicon uig-eng.masterlex.capomwn.1best.arab.flat yulghun.v1.uig-eng; do
	threecol sources/$dict > $OUTDIR/$dict
	norm-dict                $OUTDIR/$dict
	pos-tag-ify              $OUTDIR/$dict.norm
	sed "s/	UNK	/	$dict	/"   $OUTDIR/$dict >> $OUTDIR/all_lexicons
done

# Flip reverse dict
threecol  sources/yulghun.v1.eng-uig > $OUTDIR/yulghun.v1.eng-uig
norm-dict                              $OUTDIR/yulghun.v1.eng-uig --nospacysplit
mv                                     $OUTDIR/yulghun.v1.eng-uig.norm $OUTDIR/yulghun.v1.uig-eng-fromreverse
flip-dict                                                              $OUTDIR/yulghun.v1.uig-eng-fromreverse
norm-dict                                                              $OUTDIR/yulghun.v1.uig-eng-fromreverse
pos-tag-ify                                                            $OUTDIR/yulghun.v1.uig-eng-fromreverse.norm
sed "s/	UNK	/	yulghun.v1.uig-eng-fromreverse	/"                       $OUTDIR/yulghun.v1.uig-eng-fromreverse >> $OUTDIR/all_lexicons
rm $OUTDIR/yulghun.v1.eng-uig*

echo "Now processing NI translations"

cat sources/ni_{leidos_terms,ngrams_cleaned}.tsv |\
   sed 's/^ +//g;s/ *	 */	/g;s/ +$//g' >   $OUTDIR/ni-translations-2col
threecol                                   $OUTDIR/ni-translations-2col > $OUTDIR/ni-translations
flip-dict                                                                 $OUTDIR/ni-translations
norm-dict                                                                 $OUTDIR/ni-translations --targetlimit 100
pos-tag-ify                                                               $OUTDIR/ni-translations.norm
sed "s/	UNK	/	ni-translations	/"                                          $OUTDIR/ni-translations >> $OUTDIR/all_lexicons
rm                                         $OUTDIR/ni-translations-2col

echo "Now normalizing all_lexicons!"

norm-dict   $OUTDIR/all_lexicons
cp          $OUTDIR/all_lexicons.norm $OUTDIR/guessing_input_lexicon

echo "Now processing NE translations"

for dict in NameTranslation_V4and5.flat NameTranslation_Uncleaned_V2.flat; do
	# Unnormalized dictionary
	threecol sources/$dict | LC_COLLATE="UTF-8" sort | LC_COLLATE="UTF-8" uniq > $OUTDIR/$dict
	python3 tools/expand_dict.py sources/grammar.uig-v04.txt sources/english.pertainyms.txt < $OUTDIR/$dict      > $OUTDIR/$dict.expanded
	# Then normalized stuff
	norm-dict   $OUTDIR/$dict --nosplit --targetlimit 100
	pos-tag-ify $OUTDIR/$dict.norm
	
	python3 tools/expand_dict.py sources/grammar.uig-v04.txt sources/english.pertainyms.txt \
		< $OUTDIR/$dict.norm \
		> $OUTDIR/$dict.norm.expanded
	python3 tools/expand_dict.py sources/grammar.uig-v04.txt sources/english.pertainyms.txt \
		< $OUTDIR/$dict.norm.singletons \
		> $OUTDIR/$dict.norm.singletons.expanded
	pos-tag-ify $OUTDIR/$dict.norm.expanded
	# And put it into all
	sed -r "s/	(.*)	/	$dict\/\1	/" $OUTDIR/$dict.expanded                 >> $OUTDIR/all_lexicons
	sed -r "s/	(.*)	/	$dict\/\1	/" $OUTDIR/$dict.norm.expanded            >> $OUTDIR/all_lexicons.norm
	sed -r "s/	(.*)	/	$dict\/\1	/" $OUTDIR/$dict.norm.singletons.expanded >> $OUTDIR/all_lexicons.norm.singletons
	sed -r "s/	(.*)	/	$dict\/\1	/" $OUTDIR/$dict.norm                     >> $OUTDIR/guessing_input_lexicon
done

echo "Now finally POStag the big ones!"

pos-tag-ify $OUTDIR/all_lexicons.norm
pos-tag-ify $OUTDIR/all_lexicons.norm.singletons
pos-tag-ify $OUTDIR/guessing_input_lexicon

echo "Time to do all the stemming"

for f in $OUTDIR/all_lexicons{.norm,.norm.singletons}; do
	python3 tools/stem.py sources/grammar.uig-v04.txt $f
done

echo "Sort everything"

for f in $OUTDIR/*; do
	sort-safely $f
done

echo "Aaaaaand we're done!"

#python3 tools/analyze_suffixes.py sources/grammar.uig-v04.txt sources/english.pertainyms.txt \
#	< $OUTDIR/all_lexicons.norm > $OUTDIR/sbmt-demand-dict.norm
#sed '/ /d'                      $OUTDIR/sbmt-demand-dict.norm > $OUTDIR/sbmt-demand-dict.norm.nophrases

cp README $OUTDIR/README
mv $OUTDIR/guessing_input_lexicon $OUTDIR/guessing_input_lexicon.$OUTDIR
