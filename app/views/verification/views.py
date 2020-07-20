from datetime import date, datetime

from flask import Blueprint, render_template
from flask import current_app as app
from flask_security import current_user, login_required, roles_accepted

from db import get_verifiers, activity
from forms import DailySpinForm
from models import Verification

# Blueprint configuration
verification = Blueprint(
    'verification', __name__, template_folder='templates')

@verification.route('/verification/verify_queue')
@login_required
def verify_queue():
    '''
    Finds the oldest and unverified session and redirects
    to that session verification. The session must either
    be assigned to the current user id or no user id
    '''

    '''
    Logic of queue priority:
    1. Check if there are sessions that are not verified
    2. Check if any are not assigned to other users
    3. Check if any are not secondarily verified
    4. Check if any of those are not assigned to other users
    '''

    unverified_sessions = Session.query.filter(and_(
        Session.is_verified==False, Session.is_dev==False))
    chosen_session = None
    is_secondary = False
    if unverified_sessions.count() > 0:
        available_sessions = unverified_sessions.filter(
            or_(Session.verified_by==None, Session.verified_by==current_user.id)).order_by(
                Session.verified_by)

        if available_sessions.count() > 0:
            # we have an available session
            chosen_session = available_sessions[0]
            chosen_session.verified_by = current_user.id

    else:
        # check if we can secondarily verify any sesssions
        secondarily_unverified_sessions = Session.query.filter(and_(
            Session.is_secondarily_verified==False, Session.verified_by!=current_user.id,
            Session.is_dev==False))

        if secondarily_unverified_sessions.count() > 0:
            available_sessions = secondarily_unverified_sessions.filter(
                or_(Session.secondarily_verified_by==None,
                    Session.secondarily_verified_by==current_user.id)).order_by(
                        Session.verified_by)

            if available_sessions.count() > 0:
                # we have an available session
                chosen_session = available_sessions[0]
                is_secondary = True
                chosen_session.secondarily_verified_by = current_user.id

    if chosen_session is None:
        # there are no sessions left to verify
        flash("Engar lotur eftir til að greina", category="warning")
        return redirect(url_for("verify_index"))

    # Once queued, a session is assigned to a user id to avoid
    # double queueing
    db.session.commit()
    url = url_for('verify_session', id=chosen_session.id)
    if is_secondary:
        url = url + '?is_secondary={}'.format(is_secondary)
    return redirect(url)

@verification.route('/sessions/<int:id>/verify/')
@login_required
def verify_session(id):
    is_secondary = bool(request.args.get('is_secondary', False))
    form = SessionVerifyForm()
    session = Session.query.get(id)
    session_dict = {
        'id': session.id,
        'collection_id': session.collection.id,
        'is_secondary': is_secondary,
        'recordings': [],
    }
    for recording in session.recordings:
        # make sure we only verify recordings that haven't been verified
        # two times
        if (not recording.is_verified and not is_secondary) \
            or (not recording.is_secondarily_verified and is_secondary):
            session_dict['recordings'].append({
                'rec_id': recording.id,
                'rec_fname': recording.fname,
                'rec_url': recording.get_download_url(),
                'rec_num_verifies': len(recording.verifications),
                'text': recording.token.text,
                'text_file_id': recording.token.fname,
                'text_url': recording.token.get_url(),
                'token_id': recording.token.id})

            if recording.is_verified:
                # add the verification object
                session_dict['recordings'][-1]['verification'] = recording.verifications[0].dict

    return render_template('verify_session.jinja', session=session, form=form,
        delete_form=DeleteVerificationForm(), json_session=json.dumps(session_dict),
        is_secondary=is_secondary, progression_view=True)

@verification.route('/verifications', methods=['GET'])
@login_required
def verification_list():
    page = int(request.args.get('page', 1))

    verifications = Verification.query.order_by(resolve_order(Verification,
        request.args.get('sort_by', default='created_at'),
        order=request.args.get('order', default='desc')))\
        .paginate(page, per_page=app.config['VERIFICATION_PAGINATION'])

    return render_template('lists/verifications.jinja', verifications=verifications,
        section='verificatioon')

@verification.route('/verifications/<int:id>/')
@login_required
def verification_detail(id):
    verification = Verification.query.get(id)
    delete_form=DeleteVerificationForm()
    return render_template('verification.jinja', verification=verification,
        delete_form=delete_form, section='verification',)



@verification.route('/verifications/create/', methods=['POST'])
@login_required
def create_verification():
    form = SessionVerifyForm(request.form)
    try:
        if form.validate():
            is_secondary = int(form.data['num_verifies']) > 0
            verification = Verification()
            verification.set_quality(form.data['quality'])
            verification.comment = form.data['comment']
            verification.recording_id = int(form.data['recording'])
            verification.is_secondary = is_secondary
            verification.verified_by = int(form.data['verified_by'])
            db.session.add(verification)
            db.session.flush()
            verification_id = verification.id
            db.session.commit()
            recording = Recording.query.get(int(form.data['recording']))
            if is_secondary:
                recording.is_secondarily_verified = True
            else:
                recording.is_verified = True
            db.session.commit()

            insert_trims(form.data['cut'], verification_id)
            progression = User.query.get(form.data['verified_by']).progression

            # check if this was the final recording to be verified and update
            session = Session.query.get(int(form.data['session']))
            recordings = Recording.query.filter(Recording.session_id==session.id)
            num_recordings = recordings.count()
            achievements = []
            if is_secondary and num_recordings ==\
                recordings.filter(Recording.is_secondarily_verified==True).count():
                session.is_secondarily_verified = True
                db.session.commit()
            elif num_recordings == recordings.filter(Recording.is_verified==True).count():
                session.is_verified = True
                progression.num_session_verifies += 1
                progression.lobe_coins += app.config['ECONOMY']['session']['coin_reward']
                progression.experience += app.config['ECONOMY']['session']['experience_reward']

                ## check for streak
                #if not progression.has_streaked_today:
                #    num_verifies_today = Verification.query.filter(Verification.verified_by==current_user.id,
                #        (Verification.created_at+datetime.timedelta(days=1))>datetime.now())
                #    if num_verifies_today >= app.config['ECONOMY']['achievement']['streak_minimum']:
                #        progression.num_streak_days += 1
                #        if progression.num_streak_days >= app.config['ECONOMY']['achievement']['streak'][str(progression.streak_level)]:
                #            progression.streak_level += 1
                #            progression.has_streaked_today = True
                #            achievements.append('streak')
                db.session.commit()

            # update progression on user
            progression.lobe_coins += app.config['ECONOMY']['verification']['coin_reward']
            progression.experience += app.config['ECONOMY']['verification']['experience_reward']
            progression.num_verifies += 1
            progression.weekly_verifies += 1
            if not verification.recording_is_good:
                progression.num_invalid += 1

            # check for achivement updates:
            # 1. verification:
            verification_info = app.config['ECONOMY']['achievements']['verification'][str(progression.verification_level)]
            if progression.num_verifies >= verification_info['goal']:
                progression.verification_level += 1
                progression.lobe_coins += verification_info['coin_reward']
                progression.experience += verification_info['experience_reward']
                achievements.append('verification')
            # 2. bad verifications
            spy_info = app.config['ECONOMY']['achievements']['spy'][str(progression.spy_level)]
            if progression.num_invalid >= spy_info['goal']:
                progression.spy_level += 1
                progression.lobe_coins += spy_info['coin_reward']
                progression.experience += spy_info['experience_reward']
                achievements.append('spy')

            db.session.commit()

            response = {
                'id':verification_id,
                'coins': progression.lobe_coins,
                'experience': progression.experience,
                'achievements': achievements}

            return Response(json.dumps(response), status=200)
        else:
            errorMessage = "<br>".join(list("{}: {}".format(key, ", ".join(value)) for key, value in form.errors.items()))
            return Response(errorMessage, status=500)
    except Exception as error:
        app.logger.error('Error creating a verification : {}\n{}'.format(error, traceback.format_exc()))

@verification.route('/verifications/delete', methods=['POST'])
@login_required
def delete_verification():
    form = DeleteVerificationForm(request.form)
    if form.validate():
        verification = Verification.query.get(int(form.data['verification_id']))
        verified_by = verification.verified_by
        is_secondary = verification.is_secondary
        recording = Recording.query.get(verification.recording_id)
        session = Session.query.get(recording.session_id)
        session_was_verified = session.is_verified
        progression = User.query.get(verified_by).progression

        if is_secondary:
            recording.is_secondarily_verified = False
            session.is_secondarily_verified = False
        else:
            recording.is_verified = False
            session.is_verified = False
            if session_was_verified:
                progression.lobe_coins -= app.config['ECONOMY']['session']['coin_reward']
                progression.experience -= app.config['ECONOMY']['session']['experience_reward']

        progression.num_verifies -= 1
        progression.weekly_verifies -= 1
        if not verification.recording_is_good:
            progression.num_invalid -= 1

        # check for achivement updates:
        # 1. verification:
        if progression.verification_level > 0:
            verification_info = app.config['ECONOMY']['achievements']['verification'][str(progression.verification_level-1)]
            if progression.num_verifies < verification_info['goal']:
                progression.verification_level -= 1
                progression.lobe_coins -= verification_info['coin_reward']
                progression.experience -= verification_info['experience_reward']
        # 2. bad verifications
        if progression.spy_level > 0:
            spy_info = app.config['ECONOMY']['achievements']['spy'][str(progression.spy_level - 1)]
            if progression.num_invalid < spy_info['goal']:
                progression.spy_level -= 1
                progression.lobe_coins -= spy_info['coin_reward']
                progression.experience -= spy_info['experience_reward']

        # update progression on user
        progression.lobe_coins = max(0, progression.lobe_coins - app.config['ECONOMY']['verification']['coin_reward'])
        progression.experience = max(0, progression.experience - app.config['ECONOMY']['verification']['experience_reward'])

        db.session.delete(verification)
        db.session.commit()

        response = {
            'coins': progression.lobe_coins,
            'experience': progression.experience}

        return Response(json.dumps(response), status=200)
    else:
        errorMessage = "<br>".join(list("{}: {}".format(key, ", ".join(value)) for key, value in form.errors.items()))
        return Response(errorMessage, status=500)

@verification.route('/verification', methods=['GET'])
@login_required
def verify_index():
    '''
    Home screen of the verifiers
    '''
    verifiers = sorted(get_verifiers(), key=lambda v: -v.progression.weekly_verifies)
    weekly_verifies = sum([v.progression.weekly_verifies for v in verifiers])
    if weekly_verifies < app.config['ECONOMY']['weekly_challenge']['goal']:
        weekly_progress = 100*((weekly_verifies-current_user.progression.weekly_verifies)/\
            app.config['ECONOMY']['weekly_challenge']['goal'])
    else:
        weekly_progress = 100*((weekly_verifies - app.config['ECONOMY']['weekly_challenge']['goal'])%\
            app.config['ECONOMY']['weekly_challenge']['extra_interval']/\
            app.config['ECONOMY']['weekly_challenge']['extra_interval'])
    user_weekly_progress = 100*(current_user.progression.weekly_verifies/app.config['ECONOMY']['weekly_challenge']['goal'])

    verification_progress = 0
    if current_user.progression.verification_level < len(app.config['ECONOMY']['achievements']['verification'].keys()):
        verification_progress = 100*(current_user.progression.num_verifies/\
            app.config['ECONOMY']['achievements']['verification'][str(current_user.progression.verification_level)]['goal'])

    spy_progress = 0
    if current_user.progression.spy_level < len(app.config['ECONOMY']['achievements']['spy'].keys()):
        spy_progress = 100*(current_user.progression.num_invalid/\
            app.config['ECONOMY']['achievements']['spy'][str(current_user.progression.spy_level)]['goal'])

    streak_progress = 0


    show_weekly_prices, show_daily_spin = False, False
    daily_spin_form = DailySpinForm()
    if not current_user.progression.has_seen_weekly_prices:
        progression = current_user.progression
        progression.has_seen_weekly_prices = True
        db.session.commit()
        show_weekly_prices = True
    elif current_user.progression.last_spin < datetime.combine(date.today(), datetime.min.time()):
        # we dont want to show weekly prizes and spins at the same time
        # last spin was not today
        show_daily_spin = True

    activity_days, activity_counts = activity(Verification)

    # get the number of verifications per user
    return render_template('verify_index.jinja', verifiers=verifiers, weekly_verifies=weekly_verifies,
        weekly_progress=weekly_progress, user_weekly_progress=user_weekly_progress,
        verification_progress=verification_progress, spy_progress=spy_progress,
        streak_progress=streak_progress, daily_spin_form=daily_spin_form,
        progression_view=True, show_weekly_prices=show_weekly_prices, show_daily_spin=show_daily_spin,
        activity_days=activity_days, activity_counts=activity_counts)