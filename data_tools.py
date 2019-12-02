import os
from shutil import copyfile

def ds_to_merlinformat(src_dir:str, out_dir:str):
    '''
    Convert an exported dataset to a Merlin compatible
    dataset by creating a new collection at out_dir where
    each .token has been renamed to take the same name as
    the corresponding .wav.
    '''
    if os.path.exists(out_dir):
        print("out_dir exists on disk, returning")
        return False
    else:
        txt_dir = os.path.join(out_dir, 'txt')
        wav_dir = os.path.join(out_dir, 'wav')
        os.makedirs(txt_dir)
        os.makedirs(wav_dir)

    with open(os.path.join(src_dir, 'index.tsv')) as index:
        for line in index:
            wav_fname, txt_fname = line.split('\t')
            ident = os.path.splitext(wav_fname)[0]
            copyfile(os.path.join(src_dir, 'wavs', wav_fname), os.path.join(wav_dir, wav_fname))
            copyfile(os.path.join(src_dir, 'texts', txt_fname.strip()), os.path.join(txt_dir, "{}.txt".format(ident)))

if __name__ == '__main__':
    ds_to_merlinformat('/home/atli/Desktop/margret_total_old', '/home/atli/Desktop/margret_merlin')
