from flask import Blueprint, redirect, url_for
from flask_security import current_user, login_required, roles_accepted

# Blueprint configuration
configuration = Blueprint(
    'configuration', __name__, template_folder='templates')

@configuration.route('/confs/')
@login_required
@roles_accepted('admin', 'Notandi')
def conf_list():
    page = int(request.args.get('page', 1))
    confs = Configuration.query.order_by(resolve_order(Configuration,
        request.args.get('sort_by', default='created_at'),
        order=request.args.get('order', default='desc'))).paginate(page,
        per_page=app.config['CONF_PAGINATION'])
    return render_template('lists/confs.jinja', confs=confs, section='other')


@configuration.route('/confs/<int:id>/')
@login_required
@roles_accepted('admin', 'Notandi')
def conf(id):
    conf = Configuration.query.get(id)
    collections = Collection.query.filter(Collection.configuration_id==id)
    return render_template('conf.jinja', conf=conf, collections=collections,
        section='other')


@configuration.route('/confs/<int:id>/edit/', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def edit_conf(id):
    conf = Configuration.query.get(id)
    form = ConfigurationForm(obj=conf)
    if request.method == 'POST':
        try:
            form = ConfigurationForm(request.form, obj=conf)
            if form.validate():
                form.populate_obj(conf)
                db.session.commit()
                flash("Stillingum var breytt", category='success')
                return redirect(url_for("conf", id=conf.id))
        except Exception as error:
            app.logger.error('Error updating a configuration : {}\n{}'.format(error, traceback.format_exc()))
    return render_template('forms/model.jinja', form=form, type='edit',
        action=url_for('edit_conf', id=id), section='other')


@configuration.route('/confs/create/', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def create_conf():
    form = ConfigurationForm(request.form)
    if request.method == 'POST' and form.validate():
        try:
            configuration = Configuration()
            form.populate_obj(configuration)
            db.session.add(configuration)
            db.session.commit()
            return redirect(url_for('conf', id=configuration.id))
        except Exception as error:
            flash("Error creating configuration.", category="danger")
            app.logger.error("Error creating configuration {}\n{}".format(error,traceback.format_exc()))
    return render_template('forms/model.jinja', form=form,
        action=url_for('create_conf'), section='other')


@configuration.route('/confs/<int:id>/delete/', methods=['GET'])
@login_required
@roles_accepted('admin')
def delete_conf(id):
    conf = Configuration.query.get(id)
    name = conf.printlable_name
    if conf.is_default:
        flash("Ekki er hægt að eyða aðalstillingum", category='warning')
        return redirect(conf.url)
    try:
        db.session.delete(user)
        db.session.commit()
        flash(f"{name} var eytt", category='success')
    except Exception as error:
        app.logger.error('Error deleting a configuration : {}\n{}'.format(error, traceback.format_exc()))
    return redirect(url_for('rec_session_list'))