import datetime

from flask import Blueprint, request, jsonify, current_app, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_cors import cross_origin

from mydb import db
from models.models import Category
from utils import do_sql_sel


api_bp = Blueprint(
    "api_bp",
    __name__,
    template_folder="templates/rozhody",
    static_folder="static",
)

@api_bp.route("/api/categories/", methods=["GET"])
@cross_origin()
@jwt_required()
def get_categories():
    """
    return  categories
    """
    current_user = get_jwt_identity()
    categories = db.session().query(Category).filter_by(
        user_id=current_user.get('user_id')
    ).all()
    try:
        return [category.to_dict() for category in categories]
    except Exception as err:
        current_app.logger.error(f"{err}")
        abort(500, f"{err}")


@api_bp.route("/api/payments/period", methods=["GET"])
@cross_origin()
@jwt_required()
def payments_for_period():
    """
    return payments grouped by categories in some period (year, month)
    """
    current_user = get_jwt_identity()
    year = request.args.get("year", "").zfill(2)
    month = request.args.get("month", "").zfill(2)
    mono_user_id = request.args.get("mono_user_id")

    condition = []
    curr_date = datetime.datetime.now()
    if not year:
        year = f'{curr_date:%Y}'
    if not month:
        month = f'{curr_date:%m}'

    start_date = f'{year}-{int(month):02d}-01'
    end_date = f'{year if int(month) < 12 else int(year) + 1}-{int(month) + 1 if int(month) < 12 else 1:02d}-01'
    condition.append(" and p.`rdate` >= :start_date and p.`rdate` < :end_date")

    if mono_user_id:
        condition.append(" and mono_user_id = :mono_user_id")

    data = {
        "start_date": start_date,
        "end_date": end_date,
        "mono_user_id": mono_user_id,
        "user_id": current_user.get('user_id')
    }

    sql = f"""
select p.category_id, c.name,convert(sum(`amount`),UNSIGNED) as amount,
count(*) as cnt
from `payments` p left join `categories` c
on p.categoy_id = c.id
where 1=1 
and p.user_id = :user_id
and `is_deleted` = 0
and `amount` > 0
{' '.join(condition)}
group by p.category_id, c.name order by 3 desc
"""
    return do_sql_sel(sql, data)


@api_bp.route("/api/payments/years", methods=["GET"])
@cross_origin()
@jwt_required()
def payment_by_years():
    """
    return total payments grouped by years
    """
    current_user = get_jwt_identity()
    mono_user_id = request.args.get("mono_user_id")
    um_mono_user = ''
    if mono_user_id:
        um_mono_user = " and mono_user_id = :mono_user_id"
    data = {"mono_user_id": mono_user_id, "user_id": current_user.get('user_id')}

    dialect_name = db.engine.dialect.name

    if dialect_name == 'sqlite':
        substring_func = "strftime('%Y', `rdate`)"
        amount_func = "CAST(sum(`amount`) AS INTEGER)"
    elif dialect_name == 'mysql':
        substring_func = 'extract(YEAR from `rdate`)'
        amount_func = 'convert(sum(`amount`), UNSIGNED)'
    else:
        abort(400, f"Substring function not implemented for dialect: {dialect_name}")

    sql = f"""
select {substring_func} as year, {amount_func} as amount, count(*) as cnt
from `payments`
where 1=1
and `user_id` = :user_id
and `is_deleted` = 0
and `amount` > 0
{um_mono_user}
group by {substring_func} order by 1 desc
"""

    return do_sql_sel(sql, data)


@api_bp.route("/api/payments/years/<int:year>", methods=["GET"])
@cross_origin()
@jwt_required()
def months(year):
    """
    return total payments grouped by months in year
    """
    current_user = get_jwt_identity()
    mono_user_id = request.args.get("mono_user_id")
    um_mono_user = ''
    if mono_user_id:
        um_mono_user = " and mono_user_id = :mono_user_id"
    data = {
        "mono_user_id": mono_user_id,
        "user_id": current_user.get('user_id'),
        "year": str(year)
    }

    dialect_name = db.engine.dialect.name
    if dialect_name == 'sqlite':
        month_func = "strftime('%m', `rdate`)"
        year_func = "strftime('%Y', `rdate`)"
        amount_func = "CAST(sum(`amount`) AS INTEGER)"
    elif dialect_name == 'mysql':
        month_func = 'extract(MONTH from `rdate`)'
        year_func = 'extract(YEAR from `rdate`)'
        amount_func = 'convert(sum(`amount`), UNSIGNED)'
    else:
        abort(400, f"Substring function not implemented for dialect: {dialect_name}")

    sql = f"""select 
{month_func} month, {amount_func} as amount,
count(*) as cnt
from `payments`
where 1=1 and `user_id` = :user_id and {year_func} = :year
{um_mono_user}
group by {month_func} order by 1 desc
"""

    return do_sql_sel(sql, data)


@api_bp.route("/api/about", methods=["GET"])
@cross_origin()
def about():
    """
    return content of /txt/about.html
    """
    try:
        with open("txt/about.html", encoding="utf8") as f:
            data = f.read()
    except Exception as err:
        current_app.logger.error(f"{err}")
        return jsonify({"status": "error", "data": "error open about file"})

    return jsonify({"status": "ok", "data": data})
