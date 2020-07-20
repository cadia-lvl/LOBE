from flask import Blueprint, redirect, url_for
from flask_security import current_user, login_required, roles_accepted

# Blueprint configuration
shop = Blueprint(
    'shop', __name__, template_folder='templates')

@shop.route('/shop/', methods=['GET'])
@login_required
@roles_accepted('Greinir', 'admin')
def lobe_shop():
    icons = VerifierIcon.query.order_by(VerifierIcon.price).all()
    titles = VerifierTitle.query.order_by(VerifierTitle.price).all()
    quotes = VerifierQuote.query.order_by(VerifierQuote.price).all()
    fonts = VerifierFont.query.order_by(VerifierFont.price).all()
    loot_boxes = app.config['LOOT_BOXES']

    loot_box_message = request.args.get('messages', None)
    loot_box_items = []
    if loot_box_message is not None:
        for _, item in json.loads(loot_box_message).items():
            if item['type'] == 'icon':
                loot_box_items.append(VerifierIcon.query.get(item['id']))
            if item['type'] == 'title':
                loot_box_items.append(VerifierTitle.query.get(item['id']))
            if item['type'] == 'quote':
                loot_box_items.append(VerifierQuote.query.get(item['id']))

    return render_template('lobe_shop.jinja',
        icons=icons,titles=titles, quotes=quotes, loot_boxes=loot_boxes,
        fonts=fonts, loot_box_items=loot_box_items, progression_view=True,
        full_width=True,)

@shop.route('/shop/random_equip', methods=['GET'])
@login_required
@roles_accepted('Greinir', 'admin')
def random_equip():
    progression = current_user.progression
    if all(len(o) > 1 for o in [progression.owned_icons,
        progression.owned_titles, progression.owned_quotes]):
        progression.equip_random_icon()
        progression.equip_random_title()
        progression.equip_random_quote()
        db.session.commit()
        flash("Stíl var breytt", category="success")
    else:
        flash('Þú verður að eiga a.m.k. tvö stykki af hverri tegund',
            category='warning')
    return redirect(url_for('lobe_shop'))

@shop.route('/shop/loot_box/<int:rarity>', methods=['GET'])
@login_required
@roles_accepted('Greinir', 'admin')
def loot_box(rarity):
    set_price = app.config['ECONOMY']['loot_boxes']['prices'][str(rarity)]

    if set_price <= current_user.progression.lobe_coins:
        icons = VerifierIcon.query.all()
        titles = VerifierTitle.query.all()
        quotes = VerifierQuote.query.all()

        common_items = [icon for icon in icons if icon.rarity == 0] + \
            [title for title in titles if title.rarity == 0] + \
            [quote for quote in quotes if quote.rarity == 0]

        rare_items = [icon for icon in icons if icon.rarity == 1] + \
            [title for title in titles if title.rarity == 1] + \
            [quote for quote in quotes if quote.rarity == 1]

        epic_items = [icon for icon in icons if icon.rarity == 2] + \
            [title for title in titles if title.rarity == 2] + \
            [quote for quote in quotes if quote.rarity == 2]

        legendary_items = [icon for icon in icons if icon.rarity == 3] + \
            [title for title in titles if title.rarity == 3] + \
            [quote for quote in quotes if quote.rarity == 3]

        if rarity == 1:
            # we guarantee one rare item
            guaranteed_item = random.choice(rare_items)
        elif rarity == 2:
            # we guarantee one epic item
            guaranteed_item = random.choice(epic_items)
        elif rarity == 3:
            # we guarantee one legendary item
            guaranteed_item = random.choice(legendary_items)
        else:
            # we guarantee one common item
            guaranteed_item = random.choice(common_items)

        all_items = common_items + rare_items + epic_items + legendary_items
        probabilities = [app.config['ECONOMY']['loot_boxes']['rarity_weights'][str(item.rarity)] for item in all_items]
        norm_probabilities = [p_val/np.sum(probabilities) for p_val in probabilities]
        selected_items = list(np.random.choice(all_items, app.config['ECONOMY']['loot_boxes']['num_items']-1,
            p=norm_probabilities))
        selected_items.append(guaranteed_item)

        progression = current_user.progression
        progression.lobe_coins -= set_price
        types = []
        for item in selected_items:
            if type(item) == VerifierQuote:
                progression.owned_quotes.append(item)
                types.append('quote')
            if type(item) == VerifierTitle:
                progression.owned_titles.append(item)
                types.append('title')
            if type(item) == VerifierIcon:
                progression.owned_icons.append(item)
                types.append('icon')
        db.session.commit()

        loot_box_message = json.dumps({str(i):{'type': types[i], 'id': item.id} for i,item in enumerate(selected_items)})
        flash("Kaup samþykkt", category='success')
        return redirect(url_for('lobe_shop', messages=loot_box_message))

    flash("Þú átt ekki nóg fyrir þessum lukkukassa", category='warning')
    return redirect(url_for('lobe_shop'))

@shop.route('/shop/icons/<int:icon_id>/buy/<int:user_id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('Greinir')
def icon_buy(icon_id, user_id):
    user = User.query.get(user_id)
    icon = VerifierIcon.query.get(icon_id)
    progression = VerifierProgression.query.get(user.progression_id)

    if progression.fire_sale:
        price = int(icon.price*(1-progression.fire_sale_discount))
    else:
        price = icon.price

    if progression.lobe_coins >= price and icon not in progression.owned_icons:
        progression.owned_icons.append(icon)
        progression.equipped_icon_id = icon.id
        progression.lobe_coins -= price
        db.session.commit()
        flash("Kaup samþykkt.", category="success")
    else:
        flash("Kaup ekki samþykkt", category="warning")
    return redirect(url_for('lobe_shop'))

@shop.route('/shop/icons/disable/<int:user_id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('Greinir')
def icon_disable(user_id):
    user = User.query.get(user_id)
    progression = VerifierProgression.query.get(user.progression_id)
    progression.equipped_icon_id = None
    db.session.commit()
    flash("Kveikt á venjulegu merki.", category="success")
    return redirect(url_for('lobe_shop'))

@shop.route('/shop/icons/<int:icon_id>/equip/<int:user_id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('Greinir')
def icon_equip(icon_id, user_id):
    user = User.query.get(user_id)
    icon = VerifierIcon.query.get(icon_id)
    progression = VerifierProgression.query.get(user.progression_id)
    if icon in progression.owned_icons:
        progression.equipped_icon_id = icon.id
        db.session.commit()
        flash("Merki valið", category="success")
    else:
        flash("Val ekki samþykkt", category="warning")
    return redirect(url_for('lobe_shop'))

@shop.route('/shop/icons/create', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def icon_create():
    form = VerifierIconForm(request.form)
    for field in form:
        print(field)
    if request.method == 'POST' and form.validate():
        try:
            form['color'].data = str(form['color'].data)
            icon = VerifierIcon()
            form.populate_obj(icon)
            db.session.add(icon)
            db.session.commit()
            flash("Nýju merki bætt við", category="success")
            return redirect(url_for('lobe_shop'))
        except Exception as error:
            flash("Error creating verifier icon.", category="danger")
            app.logger.error("Error creating verifier icon {}\n{}".format(error,traceback.format_exc()))
    return render_template('forms/model.jinja', form=form,
        action=url_for('icon_create'), section='verification', type='create')

@shop.route('/shop/icons/<int:id>/edit/', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def icon_edit(id):
    icon = VerifierIcon.query.get(id)
    form = VerifierIconForm(obj=icon)
    try:
        if request.method == 'POST' and form.validate():
            form = VerifierIconForm(request.form, obj=icon)
            form['color'].data = str(form['color'].data)
            form.populate_obj(icon)
            db.session.commit()
            flash("Merki var breytt", category="success")
            return redirect(url_for('lobe_shop'))
    except Exception as error:
        flash("Error updating icon.", category="danger")
        app.logger.error("Error updating icon {}\n{}".format(error,traceback.format_exc()))
    return render_template('forms/model.jinja', form=form,
        action=url_for('icon_edit', id=id), section='verification', type='edit')


@shop.route('/shop/titles/<int:title_id>/buy/<int:user_id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('Greinir')
def title_buy(title_id, user_id):
    user = User.query.get(user_id)
    title = VerifierTitle.query.get(title_id)
    progression = VerifierProgression.query.get(user.progression_id)

    if progression.fire_sale:
        price = int(title.price*(1-progression.fire_sale_discount))
    else:
        price = title.price

    if progression.lobe_coins >= price and title not in progression.owned_titles:
        progression.owned_titles.append(title)
        progression.equipped_title_id = title.id
        progression.lobe_coins -= price
        db.session.commit()
        flash("Kaup samþykkt.", category="success")
    else:
        flash("Kaup ekki samþykkt", category="warning")
    return redirect(url_for('lobe_shop'))

@shop.route('/shop/titles/disable/<int:user_id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('Greinir')
def title_disable(user_id):
    user = User.query.get(user_id)
    progression = VerifierProgression.query.get(user.progression_id)
    progression.equipped_title_id = None
    db.session.commit()
    flash("Kveikt á venjulegum titil.", category="success")
    return redirect(url_for('lobe_shop'))

@shop.route('/shop/titles/<int:title_id>/equip/<int:user_id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('Greinir')
def title_equip(title_id, user_id):
    user = User.query.get(user_id)
    title = VerifierTitle.query.get(title_id)
    progression = VerifierProgression.query.get(user.progression_id)
    if title in progression.owned_titles:
        progression.equipped_title_id = title.id
        db.session.commit()
        flash("Merki valið", category="success")
    else:
        flash("Val ekki samþykkt", category="warning")
    return redirect(url_for('lobe_shop'))

@shop.route('/shop/titles/create', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def title_create():
    form = VerifierTitleForm(request.form)
    if request.method == 'POST' and form.validate():
        try:
            title = VerifierTitle()
            form.populate_obj(title)
            db.session.add(title)
            db.session.commit()
            flash("Nýjum titli bætt við", category="success")
            return redirect(url_for('lobe_shop'))
        except Exception as error:
            flash("Error creating verifier title.", category="danger")
            app.logger.error("Error creating title {}\n{}".format(error,traceback.format_exc()))
    return render_template('forms/model.jinja', form=form,
        action=url_for('title_create'), section='verification', type='create')

@shop.route('/shop/titles/<int:id>/edit/', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def title_edit(id):
    title = VerifierTitle.query.get(id)
    form = VerifierTitleForm(obj=title)
    try:
        if request.method == 'POST' and form.validate():
            form = VerifierTitleForm(request.form, obj=title)
            form.populate_obj(title)
            db.session.commit()
            flash("Titli var breytt", category="success")
            return redirect(url_for('lobe_shop'))
    except Exception as error:
        flash("Error updating title.", category="danger")
        app.logger.error("Error updating title {}\n{}".format(error,traceback.format_exc()))
    return render_template('forms/model.jinja', form=form,
        action=url_for('title_edit', id=id), section='verification', type='edit')


@shop.route('/shop/quotes/<int:quote_id>/buy/<int:user_id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('Greinir')
def quote_buy(quote_id, user_id):
    user = User.query.get(user_id)
    quote = VerifierQuote.query.get(quote_id)
    progression = VerifierProgression.query.get(user.progression_id)

    if progression.fire_sale:
        price = int(quote.price*(1-progression.fire_sale_discount))
    else:
        price = quote.price

    if progression.lobe_coins >= price and quote not in progression.owned_quotes:
        progression.owned_quotes.append(quote)
        progression.equipped_quote_id = quote.id
        progression.lobe_coins -= price
        db.session.commit()
        flash("Kaup samþykkt.", category="success")
    else:
        flash("Kaup ekki samþykkt", category="warning")
    return redirect(url_for('lobe_shop'))

@shop.route('/shop/quotes/disable/<int:user_id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('Greinir')
def quote_disable(user_id):
    user = User.query.get(user_id)
    progression = VerifierProgression.query.get(user.progression_id)
    progression.equipped_quote_id = None
    db.session.commit()
    flash("Kveikt á venjulegu slagorði.", category="success")
    return redirect(url_for('lobe_shop'))

@shop.route('/shop/quotes/<int:quote_id>/equip/<int:user_id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('Greinir')
def quote_equip(quote_id, user_id):
    user = User.query.get(user_id)
    quote = VerifierQuote.query.get(quote_id)
    progression = VerifierProgression.query.get(user.progression_id)
    if quote in progression.owned_quotes:
        progression.equipped_quote_id = quote.id
        db.session.commit()
        flash("Merki valið", category="success")
    else:
        flash("Val ekki samþykkt", category="warning")
    return redirect(url_for('lobe_shop'))


@shop.route('/shop/quotes/create', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def quote_create():
    form = VerifierQuoteForm(request.form)
    if request.method == 'POST' and form.validate():
        try:
            quote = VerifierQuote()
            form.populate_obj(quote)
            db.session.add(quote)
            db.session.commit()
            flash("Nýjum titli bætt við", category="success")
            return redirect(url_for('lobe_shop'))
        except Exception as error:
            flash("Error creating verifier quote.", category="danger")
            app.logger.error("Error creating quote {}\n{}".format(error,traceback.format_exc()))
    return render_template('forms/model.jinja', form=form,
        action=url_for('quote_create'), section='verification', type='create')


@shop.route('/shop/quotes/<int:id>/edit/', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def quote_edit(id):
    quote = VerifierQuote.query.get(id)
    form = VerifierQuoteForm(obj=quote)
    try:
        if request.method == 'POST' and form.validate():
            form = VerifierQuoteForm(request.form, obj=quote)
            form.populate_obj(quote)
            db.session.commit()
            flash("Titli var breytt", category="success")
            return redirect(url_for('lobe_shop'))
    except Exception as error:
        flash("Error updating quote.", category="danger")
        app.logger.error("Error updating quote {}\n{}".format(error,traceback.format_exc()))
    return render_template('forms/model.jinja', form=form,
        action=url_for('quote_edit', id=id), section='verification', type='edit')


@shop.route('/shop/fonts/<int:font_id>/buy/<int:user_id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('Greinir')
def font_buy(font_id, user_id):
    user = User.query.get(user_id)
    font = VerifierFont.query.get(font_id)
    progression = VerifierProgression.query.get(user.progression_id)

    if progression.fire_sale:
        price = int(font.price*(1-progression.fire_sale_discount))
    else:
        price = font.price

    if progression.experience >= price and font not in progression.owned_fonts:
        progression.owned_fonts.append(font)
        progression.equipped_font_id = font.id
        progression.experience -= price
        db.session.commit()
        flash("Kaup samþykkt.", category="success")
    else:
        flash("Kaup ekki samþykkt", category="warning")
    return redirect(url_for('lobe_shop'))

@shop.route('/shop/fonts/disable/<int:user_id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('Greinir')
def font_disable(user_id):
    user = User.query.get(user_id)
    progression = VerifierProgression.query.get(user.progression_id)
    progression.equipped_font_id = None
    db.session.commit()
    flash("Kveikt á venjulegum font.", category="success")
    return redirect(url_for('lobe_shop'))

@shop.route('/shop/fonts/<int:font_id>/equip/<int:user_id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('Greinir')
def font_equip(font_id, user_id):
    user = User.query.get(user_id)
    font = VerifierFont.query.get(font_id)
    progression = VerifierProgression.query.get(user.progression_id)
    if font in progression.owned_fonts:
        progression.equipped_font_id = font.id
        db.session.commit()
        flash("Merki valið", category="success")
    else:
        flash("Val ekki samþykkt", category="warning")
    return redirect(url_for('lobe_shop'))

@shop.route('/shop/fonts/create', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def font_create():
    form = VerifierFontForm(request.form)
    if request.method == 'POST' and form.validate():
        try:
            font = VerifierFont()
            form.populate_obj(font)
            db.session.add(font)
            db.session.commit()
            flash("Nýjum font bætt við", category="success")
            return redirect(url_for('lobe_shop'))
        except Exception as error:
            flash("Error creating verifier font.", category="danger")
            app.logger.error("Error creating verifier font {}\n{}".format(error,traceback.format_exc()))
    return render_template('forms/model.jinja', form=form,
        action=url_for('font_create'), section='verification', type='create')

@shop.route('/shop/fonts/<int:id>/edit/', methods=['GET', 'POST'])
@login_required
@roles_accepted('admin')
def font_edit(id):
    font = VerifierFont.query.get(id)
    form = VerifierFontForm(obj=font)
    try:
        if request.method == 'POST' and form.validate():
            form = VerifierFontForm(request.form, obj=font)
            form.populate_obj(font)
            db.session.commit()
            flash("Font var breytt", category="success")
            return redirect(url_for('lobe_shop'))
    except Exception as error:
        flash("Error updating font.", category="danger")
        app.logger.error("Error updating font {}\n{}".format(error,traceback.format_exc()))
    return render_template('forms/model.jinja', form=form,
        action=url_for('font_edit', id=id), section='verification', type='edit')
