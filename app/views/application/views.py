from flask import Blueprint, redirect, url_for
from flask_security import current_user, login_required, roles_accepted

# Blueprint configuration
application = Blueprint(
    'application', __name__, template_folder='templates')

@application.route("/applications/")
@login_required
@roles_accepted("admin")
def applications():
    page = int(request.args.get('page', 1))
    applications = Application.query.order_by(resolve_order(Application,
        request.args.get('sort_by', default='created_at'),
        order=request.args.get('order', default='desc'))).paginate(page,
        per_page=50)
    return render_template('lists/applications.jinja', applications=applications,
        section='application')


@application.route('/applications/<int:id>/')
@login_required
@roles_accepted('admin')
def application_detail(id):
    page = int(request.args.get('page', 1))
    application = Application.query.get(id)
    recordings = Recording.query.filter(
        Recording.user_id == application.user_id
    ).order_by(
        resolve_order(Recording, request.args.get('sort_by', default='created_at'),
            order=request.args.get('order', default='desc'))
    ).paginate(page, app.config['RECORDING_PAGINATION'])
    return render_template('application.jinja', application=application,
                           recordings=recordings, section='application')


@application.route('/applications/<int:id>/delete/', methods=['GET'])
@login_required
@roles_accepted('admin')
def delete_application(id):
    application = Application.query.get(id)
    try:
        db.session.delete(application)
        db.session.commit()
        flash("Umsókn var eytt", category='success')
    except Exception:
        flash("Ekki gekk að eyða umsókn", category='warning')
    return redirect(url_for("applications"))


@application.route("/postings/")
@login_required
@roles_accepted("admin")
def postings():
    page = int(request.args.get('page', 1))
    postings = Posting.query.order_by(resolve_order(Posting,
        request.args.get('sort_by', default='created_at'),
        order=request.args.get('order', default='desc'))).paginate(page,
        per_page=20)
    return render_template('lists/postings.jinja', postings=postings,
        section='posting')


@application.route('/postings/<int:id>/')
@login_required
@roles_accepted('admin')
def posting_detail(id):
    return render_template('posting.jinja', posting=Posting.query.get(id),
        section='posting')


@application.route('/postings/<int:id>/edit/', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def edit_posting(id):
    posting = Posting.query.get(id)
    form = PostingForm(obj=posting)

    # Hack to make utterance field readonly
    if form.utterances.render_kw:
        form.utterances.render_kw["readonly"] = "readonly"
    else:
        form.utterances.render_kw = {"readonly": "readonly"}

    if request.method == "POST":
        form = PostingForm(request.form)
        if form.validate():
            form.populate_obj(posting)
            db.session.add(posting)
            db.session.commit()
            return redirect(url_for("posting", id=posting.id))

    return render_template('forms/model.jinja', form=form, type='edit',
                           action=url_for('edit_posting', id=id))


@application.route('/posting/<int:id>/delete/', methods=['GET'])
@login_required
@roles_accepted('admin')
def delete_posting(id):
    posting = Posting.query.get(id)
    try:
        db.session.delete(posting)
        db.session.commit()
        flash("Auglýsingu var eytt", category='success')
    except Exception:
        flash("Ekki gekk að eyða auglýsingu", category='warning')
    return redirect(url_for("postings"))


@application.route('/apply/<uuid:posting_uuid>/', methods=['GET', 'POST'])
def new_application(posting_uuid):
    posting = Posting.query.filter(Posting.uuid == str(posting_uuid)).first()
    form = ApplicationForm(request.form)
    if request.method == "POST":
        if form.validate():
            application = Application()
            form.populate_obj(application)
            application.posting_id = posting.id
            try:
                new_user = user_datastore.create_user(
                    name=form.data["name"],
                    email=form.data["email"],
                    password=None,
                    roles=[]
                )
                form.populate_obj(new_user)
                db.session.commit()
            except IntegrityError as e:
                app.logger.error("Could not create user for application, email already in use")
                flash("Þetta netfang er nú þegar í notkun", category='error')
                return redirect(
                    url_for("new_application", posting_uuid=posting_uuid))
            application.user_id = new_user.id
            db.session.add(application)
            db.session.commit()
            return redirect(url_for("record_session", collection_id=posting.collection) + f"?user_id={new_user.id}")

    return render_template('apply.jinja', form=form, type='create', posting=posting,
                           action=url_for('new_application', posting_uuid=posting_uuid))


@application.route('/application-success/', methods=['GET'])
def application_success():
    return render_template("application_success.jinja")


@application.route('/postings/create/', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def create_posting():
    form = PostingForm(request.form)
    if request.method == "POST":
        if form.validate():

            posting = Posting()
            form.populate_obj(posting)
            db.session.add(posting)
            db.session.flush()  # To generate defaults for posting

            collection_form = CollectionForm(data={
                "name": f"{posting.name}",
                "configuration_id": DEFAULT_CONFIGURATION_ID,
                "sort_by": "random",
                "is_multi_speaker": True,
            })
            collection = insert_collection(collection_form)

            posting.collection = collection.id

            tokens = []
            for utterance in posting.utterances.split("\n"):
                token = Token(text=utterance, original_fname="", collection_id=collection.id)
                db.session.add(token)
                tokens.append(token)

            collection.update_numbers()
            db.session.commit()
            for token in tokens:
                token.save_to_disk()
            db.session.commit()

            return redirect(url_for("posting", id=posting.id))

    return render_template('forms/model.jinja', form=form, type='create',
                           action=url_for('create_posting'))