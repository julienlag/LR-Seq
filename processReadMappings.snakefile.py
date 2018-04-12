rule integratePolyaAndSjInfo:
	input:
		polyA = "mappings/" + "removePolyAERCCs/{techname}_{capDesign}_{barcodes}.polyAsitesNoErcc.bed",
		SJs = "mappings/" + "getIntronMotif/{techname}_{capDesign}_{barcodes}.transcripts.tsv"
	output: temp("mappings/" + "integratePolyaAndSjInfo/{techname}_{capDesign}_{barcodes}.polyA+SJ.strandInfo.tsv")
	shell:
		'''
cat {input.polyA} | cut -f4,6 | awk '$2!="."'| sort > $TMPDIR/reads.polyA.strandInfo.tsv
cat {input.SJs} | skipcomments | cut -f 1,2 | awk '$2!="."' | sort> $TMPDIR/reads.SJ.strandInfo.tsv
cat $TMPDIR/reads.polyA.strandInfo.tsv $TMPDIR/reads.SJ.strandInfo.tsv | awk '$2!="."'| sort|uniq > {output}
		'''

rule strandGffs:
	input:
		gff = "mappings/" + "readBedToGff/{techname}_{capDesign}_{barcodes}.merged.gff",
		strandInfo = "mappings/" + "integratePolyaAndSjInfo/{techname}_{capDesign}_{barcodes}.polyA+SJ.strandInfo.tsv"
	output: temp("mappings/" + "strandGffs/{techname}_{capDesign}_{barcodes}.stranded.gff")
	shell:
		'''
get_right_transcript_strand.pl {input.gff} {input.strandInfo} | fgrep -v ERCC- | sortgff> {output}

		'''

rule highConfidenceReads:
	input:
		transcriptStrandInfo = "mappings/" + "getIntronMotif/{techname}_{capDesign}_{barcodes}.transcripts.tsv",
		strandedReads = "mappings/" + "strandGffs/{techname}_{capDesign}_{barcodes}.stranded.gff"
	output:
		"mappings/" + "highConfidenceReads/{techname}_{capDesign}_{barcodes}.strandedHCGMs.gff.gz"
	shell:
		'''
#select read IDs with canonical GT|GC/AG and high-confidence SJs
cat {input.transcriptStrandInfo} | skipcomments | awk '$6==1 && $7==1' | cut -f1 | sort|uniq > $TMPDIR/reads.hcSJs.list
wc -l $TMPDIR/reads.hcSJs.list
set +e
fgrep -w -f $TMPDIR/reads.hcSJs.list {input.strandedReads} > $TMPDIR/gtag.gff
set -e
wc -l $TMPDIR/gtag.gff
cat {input.strandedReads} | extractGffAttributeValue.pl transcript_id | sort|uniq -u > $TMPDIR/tmp
set +e
fgrep -w -f $TMPDIR/tmp {input.strandedReads} > $TMPDIR/tmp2
set -e
cat $TMPDIR/tmp2 | fgrep -v ERCC- > $TMPDIR/monoPolyA.gff
 echo $?
cat $TMPDIR/gtag.gff $TMPDIR/monoPolyA.gff | sortgff |gzip> {output}
 echo $?
		'''


rule getHCGMstats:
	input:
		reads = "mappings/" + "mergeSizeFracBams/{techname}_{capDesign}_{barcodes}.merged.bam",
		hcgms = "mappings/" + "highConfidenceReads/{techname}_{capDesign}_{barcodes}.strandedHCGMs.gff.gz"
	output: config["STATSDATADIR"] + "{techname}_{capDesign}.{barcodes}.HCGMs.stats.tsv"
	shell:
		'''
mappedReads=$(samtools view  -F 4 {input.reads}|cut -f1|sort|uniq|wc -l)
hcgms=$(zcat {input.hcgms} | extractGffAttributeValue.pl transcript_id | sort|uniq|wc -l)
echo -e "{wildcards.techname}\t{wildcards.capDesign}\t{wildcards.barcodes}\t$mappedReads\t$hcgms" | awk '{{print $0"\t"$5/$4}}' > {output}
		'''

rule aggHCGMCapDesignStats:
	input: lambda wildcards: expand(config["STATSDATADIR"] + "{techname}_{capDesign}.{barcodes}.HCGMs.stats.tsv", filtered_product, techname=wildcards.techname, capDesign=wildcards.capDesign, barcodes=BARCODES)
	output: config["STATSDATADIR"] + "{techname}_{capDesign}.HCGMs.stats.tsv"
	shell:
		'''
totalMapped=$(cat {input} | cut -f4 | sum.sh)
totalHCGMs=$(cat {input} | cut -f5 | sum.sh)
echo -e "{wildcards.techname}\t{wildcards.capDesign}\t$totalMapped\t$totalHCGMs" | awk '{{print $0"\t"$4/$3}}' > {output}
		'''

rule aggHCGMStats:
	input: lambda wildcards: expand(config["STATSDATADIR"] + "{techname}_{capDesign}.HCGMs.stats.tsv", techname=TECHNAMES, capDesign=CAPDESIGNS)
	output: config["STATSDATADIR"] + "all.HCGMs.stats.tsv"
	shell:
		'''
echo -e "seqTech\tcorrectionLevel\tcapDesign\tcategory\tcount" > {output}
cat {input} | awk '{{print $1"\\t"$2"\\tnonHCGM\\t"$3-$4"\\n"$1"\\t"$2"\\tHCGM\\t"$4}}' | sed 's/Corr/\t/' | sort >> {output}
		'''

rule plotHCGMStats:
	input: config["STATSDATADIR"] + "all.HCGMs.stats.tsv"
	output: config["PLOTSDIR"] + "all.HCGMs.stats.{ext}"
	shell:
		'''
echo "library(ggplot2)
library(plyr)
library(scales)
dat <- read.table('{input}', header=T, as.is=T, sep='\\t')
ggplot(data=dat, aes(x=factor(correctionLevel), y=count, fill=category)) +
geom_bar(stat='identity') + scale_fill_manual(values=c('HCGM' = '#25804C', 'nonHCGM' = '#FB3B24')) + facet_grid( seqTech ~ capDesign)+ ylab('# mapped reads') + xlab('Correction level (k-mer size)') + guides(fill = guide_legend(title='Category'))+ scale_y_continuous(labels=scientific)+
{GGPLOT_PUB_QUALITY}
ggsave('{output}', width=7, height=3)
" > {output}.r
cat {output}.r | R --slave

		'''




# rule nonAnchoredMergeReadsCompmerge:
# 	input: "mappings/" + "highConfidenceReads/{techname}_{capDesign}_{barcodes}.strandedHCGMs.gff.gz"
# 	output: "mappings/" + "nonAnchoredMergeReads/{techname}_{capDesign}_{barcodes}.compmerge.gff"
# 	shell:
# 		'''
# zcat {input} > $TMPDIR/$(basename {input})
# /nfs/no_backup_isis/rg/0ld_users/sdjebali/bin/compmerge $TMPDIR/$(basename {input}) -o {output}
# #$TMPDIR/$(basename {output})
# #cat $TMPDIR/$(basename {output}) | processCompmerge.pl - {wildcards.techname}_{wildcards.capDesign}_{wildcards.barcodes}.noAnchor. |sortgff > {output}
# 		'''

rule nonAnchoredMergeReads:
	input: "mappings/" + "highConfidenceReads/{techname}_{capDesign}_{barcodes}.strandedHCGMs.gff.gz"
	output: "mappings/" + "nonAnchoredMergeReads/{techname}_{capDesign}_{barcodes}.tmerge.gff"
	shell:
		'''
zcat {input} > $TMPDIR/$(basename {input})
tmerge.pl $TMPDIR/$(basename {input}) |sortgff > {output}
#$TMPDIR/$(basename {output})
#cat $TMPDIR/$(basename {output}) | processCompmerge.pl - {wildcards.techname}_{wildcards.capDesign}_{wildcards.barcodes}.noAnchor. |sortgff > {output}
		'''

