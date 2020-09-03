import librosa
import numpy as np


def load_sample(path: str):
    y, sr = librosa.core.load(path, sr=None, mono=True)
    return y, sr


def find_segment(
    y: np.ndarray,
    sr: int,
    top_db: int = 10
):
    '''
    Notes:
    * We add a 0.25 sec of padding to the region to avoid cut-offs.
    * Some microphones will generate a short and loud popping sound
    at the start of recording. To avoid this, we don't consider the
    first 0.5 seconds of each recording for silence detection.
    '''
    cut_off = librosa.time_to_samples(0.5, sr=sr)
    y_cut = y[cut_off:-1]
    y_t, index = librosa.effects.trim(y_cut, top_db=top_db)
    index += cut_off
    index[0] -= cut_off/2
    index[1] += cut_off/2
    index = librosa.core.samples_to_time(index, sr=sr)
    return index


def check_sample(y: np.ndarray, checks: list):
    '''
    Returns True if sample passes all checks.
    Input arguments:
    * y (np.ndarray): A [n] shaped numpy array containing the signal
    * checks (list): A list of callable checks that return False if
    the sample passes the check
    '''
    for check in checks:
        if check(y):
            return True, check.__name__
    return False


def signal_is_too_high(
    y: np.ndarray,
    thresh: float = -4.5,
    num_frames: int = 1
):
    '''
    If the signal exceeds the treshold for a certain number of frames or
    more consectuively, it is deemed too high
    Input arguments:
    * y (np.ndarray): A [n] shaped numpy array containing the signal
    * thresh (float=-4.5): A db threshold
    * num_frames (int=20): A number of frames
    '''
    db = librosa.amplitude_to_db(y)
    thresh_count = 0
    for i in range(len(db)):
        if db[i] > thresh:
            thresh_count += 1
            if thresh_count == num_frames:
                return True
        else:
            thresh_count = 0
    return False


def signal_is_too_low(y: np.ndarray, thresh: float = -15):
    '''
    If the signal never exceeds the treshold it is deemed too low
    Input arguments:
    * y (np.ndarray): A [n] shaped numpy array containing the signal
    * thresh (float=-18): A db threshold
    '''
    db = librosa.amplitude_to_db(y)
    return not any(db_val > thresh for db_val in db)
