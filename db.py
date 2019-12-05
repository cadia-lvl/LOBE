from models import db, Collection, Session, Token
from concurrent.futures import ProcessPoolExecutor
from functools import partialmethod
import multiprocessing
import os

def create_tokens(collection_id, files, is_g2p):
    tokens = []
    for file in files:
        if is_g2p:
            i_f = file.stream.read().decode("utf-8").split('\n')
            for line in i_f:
                try:
                    text, src, scr, *pron = line.split('\t')[0:]
                    pron = '\t'.join(p for p in pron)
                    token = Token(text, file.filename, collection_id, score=scr,
                        pron=pron, source=src)
                    tokens.append(token)
                    db.session.add(token)
                except ValueError:
                    continue
        else:
            content = file.stream.read().decode("utf-8").strip().split('\n')
            for c in content:
                # we split each file by new lines
                if c[-1] == ',':
                    # this is a hack for the SQL stuff.
                    c = c[:-1]
                token = Token(c, file.filename, collection_id)
                tokens.append(token)
                # add token to database
                db.session.add(token)
    db.session.commit()

    # save token text to file
    for token in tokens:
        token.save_to_disk()
    db.session.commit()

    return tokens


def insert_collection(form):
    collection = Collection(form.name.data)
    if form.assigned_user.data is not None:
        collection.assigned_user_id = form.assigned_user.data.id
    db.session.add(collection)
    db.session.flush()


    # create dirs for tokens and records
    for dir in [collection.get_record_dir(), collection.get_token_dir()]:
        if not os.path.exists(dir): os.makedirs(dir)
        else:
            raise ValueError("""
                For some reason, we are about to create a collection with the
                same primary key as a previous collection. This could happen
                for example if 2 databases are used on the same machine. If
                this error occurs, the current environment has to change the
                DATA_BASE_DIR, TOKEN_DIR, RECORD_DIR flask environment variables
                to point to some other place.""")

    db.session.commit()
    return collection

def newest_collections(num=4):
    ''' Get the num newest collections '''
    return Collection.query.order_by(Collection.created_at.desc()).limit(num)


def newest_sessions(user_id, num=4):
    ''' Get the num newest collections '''
    return Session.query.filter(Session.user_id==user_id,).order_by(Session.created_at.desc()).limit(num)