import os
import json
from shutil import copyfile


def ds_to_merlinformat(
    src_dir: str,
    out_dir: str,
    use_json: bool = True,
    speaker_name: str = None
):
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

    if use_json:
        with open(os.path.join(src_dir, 'info.json')) as json_f:
            info = json.load(json_f)
            for record_id, item in info.items():
                wav_fname = item['collection_info']['recording_fname']
                txt_fname = item['collection_info']['text_fname']
                speaker_name = item['collection_info']['user_name']
                copy_to_merlin(src_dir, wav_dir, txt_dir, wav_fname, txt_fname,
                               speaker_name)
    else:
        with open(os.path.join(src_dir, 'index.tsv')) as index:
            for line in index:
                wav_fname, txt_fname = line.split('\t')
                copy_to_merlin(src_dir, wav_fname, txt_fname, speaker_name)


def copy_to_merlin(
    src_dir: str,
    wav_dir: str,
    txt_dir: str,
    wav_fname: str,
    txt_fname: str,
    speaker_name: str
):
    ident = os.path.splitext(wav_fname)[0]
    copyfile(
        os.path.join(src_dir, 'audio', speaker_name, wav_fname),
        os.path.join(wav_dir, wav_fname))
    copyfile(
        os.path.join(src_dir, 'text', txt_fname.strip()),
        os.path.join(txt_dir, "{}.txt".format(ident)))