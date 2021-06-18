import json
import random
import numpy as np
import traceback

from datetime import date, datetime

from flask import redirect, url_for, request, render_template, flash, Blueprint
from flask import current_app as app
from flask_security import current_user, login_required, roles_accepted

from lobe.db import get_verifiers, get_verifiers_and_admins
from lobe.models import (PostAward, User, VerifierIcon, VerifierFont, VerifierTitle,
                         VerifierQuote, VerifierProgression, Recording, db,
                         SocialPost, PostAward)
from lobe.forms import (DailySpinForm, VerifierIconForm, VerifierTitleForm,
                        VerifierQuoteForm, VerifierFontForm)

feed = Blueprint(
    'feed', __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/feed/static')

@feed.route('/lobe_feed/', methods=['GET'])
@login_required
@roles_accepted('Greinir', 'admin')
def lobe_feed():
    posts = SocialPost.query.order_by(SocialPost.created_at)
    verifiers = sorted(
        get_verifiers_and_admins(),
        key=lambda v: -v.progression.weekly_verifies)
    return render_template(
        'lobe_feed.jinja',
        posts=posts,
        verifiers=verifiers,
        )
     
        
@feed.route('/feed/post_recording/<int:recording_id>/', methods=['GET'])
@login_required
@roles_accepted('Greinir', 'admin')
def post_recording_feed(recording_id):
    if current_user.progression.experience >= 100:
        recording = Recording.query.get(recording_id)
        post = SocialPost(current_user.id, recording.id)
        db.session.add(post)
        db.session.commit()
        if post:
            flash("Upptaka hengd á vegg", category="success")
            current_user.progression.experience -= 100
            db.session.commit()
        else:
            flash("Ekki tókst að hengja upptöu á vegg", category="warning")
    else:
        flash("Ekki næg innistæða", category="warning")
    return redirect(url_for('feed.lobe_feed'))
        
        
@feed.route('/feed/award_post/<int:post_id>/basic', methods=['GET'])
@login_required
@roles_accepted('Greinir', 'admin')
def basic_award_post(post_id):
    if current_user.progression.experience >= 50:
        post = SocialPost.query.get(post_id)
        award = PostAward(current_user.id, post, 50)
        db.session.add(award)
        db.session.commit()
        if award:
            current_user.progression.experience -= 50
            post.user.progression.experience += 50
            flash("Verðlaunað", category="success")
        else:
            flash("Ekki tókst að verðlauna", category="warning")
    else:
        flash("Ekki næg innistæða", category="warning")
    return redirect(url_for('feed.lobe_feed'))
        
