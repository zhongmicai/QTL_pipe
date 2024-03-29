#!/opt/Python/2.7.3/bin/python
import sys
from collections import defaultdict
from collections import OrderedDict
import numpy as np
import re
import os
import argparse
import glob
from Bio import SeqIO
sys.path.append('/rhome/cjinfeng/BigData/software/ProgramPython/lib')
from utility import gff_parser, createdir

def usage():
    test="name"
    message='''
python Fix_Bam_ID_multi_lib.py > Bam_fixID.info
This script deal with issue 2. First, we produce a detailed table of all the libraries for all the RILs. Second, for these RILs have two libraries, we keep newest one if they are different. we keep both if they are same. Third, For these have three or more libraries we create table and correction by manual inspection. 

Fix Bam ID by the following ways:
0. All the files from Sofia's genotype results were linked to Bam_FixID
1. For FC251, some index were assigned incorrect. We replace the whole flowcell by new process files.
2. For RILs have multi libraries, we know some are wrong. We correct these by using the right libraries.

    '''
    print message

def fasta_id(fastafile):
    fastaid = defaultdict(str)
    for record in SeqIO.parse(fastafile,"fasta"):
        fastaid[record.id] = 1
    return fastaid

#Sample  #Read   Average Total   Depth   Mapped_Depth    Mapped_rate     #Library        FileName
#RIL1    23383054        100     2338305400      6.2857672043    6.13189677419   0.975520819479  1       Bam_fixID/RIL1_0_CGTACG_FC153L5.recal.bam
def read_depth(infile):
    data = defaultdict(str)
    with open (infile, 'r') as filehd:
        for line in filehd:
            line = line.rstrip()
            if len(line) > 2 and line.startswith(r'RIL'): 
                unit = re.split(r'\t',line)
                lib  = re.split(r'\.', os.path.split(unit[-1])[1])[0]
                data[lib] = '%0.2f' %(float(unit[5]))
    return data


#Lib1    Lib2    Similarity      Total_Shared_SNP_Site   Total_Identical_SNP_Sites       Lib1_SNP        Lib2_SNP
#RIL100_0_ATCACG_FC251L2 RIL100_0_TGACCA_FC0813L3        NA      0       0       51      76693
#RIL100_0_ATCACG_FC251L2 RIL102_0_ATGTCA_FC197L6 NA      0       0       51      105418
def read_similarity(infile):
    data1 = defaultdict(lambda : str())
    data2 = defaultdict(lambda : defaultdict(lambda : str()))
    with open (infile, 'r') as filehd:
        for line in filehd:
            line = line.rstrip()
            if len(line) > 2 and line.startswith(r'RIL'): 
                unit = re.split(r'\t',line)
                compare = sorted([unit[0], unit[1]])
                data1[':'.join(compare)] = unit[2] if unit[2] == 'NA' else '%0.2f' %(float(unit[2]))
                if not unit[2] == 'NA':
                    if float(unit[2]) > 0.9:
                        data2[unit[0]][unit[1]] = unit[2] if unit[2] == 'NA' else '%0.2f' %(float(unit[2]))
    return data1, data2




def readtable(infile):
    data = defaultdict(str)
    with open (infile, 'r') as filehd:
        for line in filehd:
            line = line.rstrip()
            if len(line) > 2: 
                unit = re.split(r'\t',line)
                if not data.has_key(unit[0]):
                    data[unit[0]] = unit[1]
    return data

#fix fc251 by replace with new one
def fix_fc251(work_dir, fc251_fixed):
    files1 = os.listdir(work_dir)
    r = re.compile(r'FC251')
    removed = defaultdict(lambda : str())
    added   = defaultdict(lambda : str())
    for f1 in sorted(files1):
        if r.search(f1):
            f1_fp = '%s/%s' %(work_dir, f1)
            unit1 = re.split(r'_', f1)
            ril1  = unit1[0]
            removed[ril1] = 1
            os.system('rm %s' %(f1_fp))
    files2 = os.listdir(fc251_fixed)
    for f2 in sorted(files2):
        if r.search(f2):
            f2_fp ='%s/%s' %(fc251_fixed, f2)
            unit2 = re.split(r'_', f2)
            ril2  = unit2[0]
            added[ril2] = 1
            os.system('rm %s/%s' %(work_dir, f2))
            os.system('ln -s %s %s/' %(f2_fp, work_dir))
    print 'Removed %s RILs: %s' %(len(removed.keys()), ','.join(sorted(removed.keys())))
    print 'Added %s RILs: %s' %(len(added.keys()), ','.join(sorted(added.keys())))

def clean_landrace(work_dir):
    list1 = glob.glob('%s/%s_*' %(work_dir, 'A160'))
    list2 = glob.glob('%s/%s_*' %(work_dir, 'RILA123'))
    for f in list1:
        print f
        os.system('rm %s' %(f))
    for f in list2:
        print f
        os.system('rm %s' %(f))

def flowcell_date():
    flowcell = {
    "FC133":'120710',  #date not lable, assigned to oldest
    "FC153":'120810',
    "FC193":'130522',
    "FC197":'130624',
    "FC205":'130708',
    "FC251":'140624',
    "FC271":'141202',
    "FC279":'141217',
    "FC0813":'130901', #date not lable, assigned to between FC205 and FC251 which roughly right
    "FC1213":'130902'  #date not lable, assigned to between FC205 and FC251 which roughly right
    }
    return flowcell

#Bam_fixID/RIL100_0_ATCACG_FC251L2.recal.bam 
def multi_lib(work_dir, lib_depth, lib_dupli_pair, lib_dupli_single):
    data = defaultdict(lambda : defaultdict(lambda : str()))
    bams = glob.glob('%s/*.recal.bam' %(work_dir))
    #create dict of RIL->lib->flowcell
    for bam in sorted(bams):
        lib = re.split(r'\.', os.path.split(bam)[1])[0]
        ril = re.sub(r'RIL', r'' ,re.split(r'_', lib)[0])
        flowcell = re.split(r'_', lib)[-1][:-2]
        data[ril][lib] = flowcell
        #print lib, ril, flowcell 
    #rank the lib for each RIL by sequenced date of flowcell
    fc_date = flowcell_date()
    print 'RIL\tLib:Date:Depth'
    for ril in sorted(data.keys(), key=int):
        if len(data[ril].keys()) == 1:
            lib = data[ril].keys()[0]
            #lib have similar library with other rils
            similar = 'NA'
            if lib_dupli_single.has_key(lib):
                dupli = []
                for lib1 in sorted(lib_dupli_single[lib].keys()):
                    dupli.append('%s:%s:%s' %(lib, lib1, lib_dupli_single[lib][lib1]))
                similar = '\t'.join(dupli)
            print 'RIL%s\t%s:%s:%s\t\t\t\t%s' %(ril, lib, fc_date[data[ril][lib]], lib_depth[lib],similar)
        elif len(data[ril].keys()) > 1:
            lib_dict = defaultdict(lambda : str())
            for lib in data[ril].keys():
                lib_date = fc_date[data[ril][lib]]
                lib_dict[lib] = lib_date
            #sort and output
            lib_dict_sorted = OrderedDict(sorted(lib_dict.items(), key=lambda x: x[1], reverse=True))
            ril_info = []
            for lib in lib_dict_sorted.keys():
                lib_info = '%s:%s:%s' %(lib, lib_dict_sorted[lib], lib_depth[lib])
                ril_info.append(lib_info)
            #fill list to 4 culumn
            ril_info.extend(['']*(4-len(ril_info)))

            #similar between lib for one ril
            similar = defaultdict(lambda : str())
            similar_list = []
            for lib in lib_dict_sorted.keys():
                for lib1 in lib_dict_sorted.keys():
                    pair = ':'.join(sorted([lib, lib1]))
                    if not lib == lib1 and not similar.has_key(pair):
                        similar[pair] = lib_dupli_pair[pair]
                        similar_list.append('%s:%s' %(pair, lib_dupli_pair[pair]))
            #lib similar with other library
            similar_lib = ''
            for lib in lib_dict_sorted.keys():
                if lib_dupli_single.has_key(lib):
                    dupli = []
                    for lib1 in sorted(lib_dupli_single[lib].keys()):
                        #exclude these from same ril
                        pair = ':'.join(sorted([lib, lib1]))
                        if not similar.has_key(pair):
                            dupli.append('%s:%s:%s' %(lib, lib1, lib_dupli_single[lib][lib1]))
                    similar_lib = '\t'.join(dupli)
            print 'RIL%s\t%s\t%s\t%s' %(ril, '\t'.join(ril_info), '\t'.join(similar_list), similar_lib)
       
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input')
    parser.add_argument('-o', '--output')
    parser.add_argument('-v', dest='verbose', action='store_true')
    args = parser.parse_args()
    
    work_dir    = '/rhome/cjinfeng/BigData/00.RD/RILs/QTL_pipe/input/fastq/Bam_fixID'    
    fc251_fixed = '/rhome/cjinfeng/BigData/00.RD/RILs/Problem_RILs/bin/RILs_genotype/genotypes/MSU_r7.corrected'
    #clean files not RILs
    #clean_landrace(work_dir)
    #fix flowcell 251, use new genotype data from fc251_fixed to replace the old one
    #fix_fc251(work_dir, fc251_fixed) 

    #For these libraries with multi libraries we collection information (flowcell, depth, data) and picked the newest one as representive libraries.
    lib_depth = read_depth('Bam_fixID.bam.stat')
    lib_dupli_pair, lib_dupli_single = read_similarity('Bam_fixID.SNP.similarity')
    multi_lib(work_dir, lib_depth, lib_dupli_pair, lib_dupli_single)

if __name__ == '__main__':
    main()

