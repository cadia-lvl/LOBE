import os

def ds_to_merlinformat(src_dir:str):
    '''
    Convert an exported dataset to a Merlin compatible
    dataset.
    '''
    with open(os.path.join(src_dir, 'index.tsv')) as index:
        for line in index:
            wav_fname, txt_fname = line.split('\t')
            ident = os.path.splitext(wav_fname)[0]
            os.rename(os.path.join(src_dir, 'text', txt_fname.strip()), os.path.join(src_dir, 'text', "{}.token".format(ident)))