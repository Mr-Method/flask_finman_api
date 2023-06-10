# _*_ coding:UTF-8 _*_
import logging
import time
import datetime
import random

import requests

from flask import current_app, request
from sqlalchemy import and_

from api.config.schemas import ConfigTypes
from api.mono.services import get_mono_users_
from mydb import db
from models.models import Category, Config, MonoUser, Payment, User

from config import mono_api_url


mono_logger = logging.getLogger('mono')
"""
url for webhook:
https://script.google.com/macros/s/AKfycbxq8R2y9ugmDmfYDAp9rf5MEUs_5lf2SNT_Cc0u_R3KYTfYMPvc/exec

https://api.monobank.ua/
POST /personal/webhook
{
  "webHookUrl": "string"
}
"""

def get_mono_user_info__(mono_user_id: int):
    mono_user_token = None
    result = {}

    mono_user_token = get_mono_user_token(mono_user_id)

    if not mono_user_token:
        current_app.logger.error(f'Token not found. mono_user_id: {mono_user_id}')
        abort(401, f'Token not found. mono_user_id:{mono_user_id}')

    header = {"X-Token": mono_user_token}

    url = f"{mono_api_url}/personal/client-info"

    try:
        r = requests.get(url, headers=header)
    except Exception as err:
        current_app.logger.error(f"{err}")
        abort(400, f'Bad request: {err}\n{r.text}')

    result = r.json()
    result['this_api_webhook'] = request.url_root + f'api/mono/users/{mono_user_id}/webhook'
    result['mono_user_id'] = mono_user_id

    return result


def _mcc(mcc):
    if (
        mcc
        in (
            4011,
            4111,
            4112,
            4131,
            4304,
            4411,
            4415,
            4418,
            4457,
            4468,
            4511,
            4582,
            4722,
            4784,
            4789,
            5962,
            6513,
            7011,
            7032,
            7033,
            7512,
            7513,
            7519,
        )
        or mcc in range(3000, 4000)
    ):
        return "Подорожі"
    elif (
        mcc
        in (
            4119,
            5047,
            5122,
            5292,
            5295,
            5912,
            5975,
            5976,
            5977,
            7230,
            7297,
            7298,
            8011,
            8021,
            8031,
            8049,
            8050,
            8062,
            8071,
            8099,
        )
        or mcc in range(8041, 8044)
    ):
        return "Краса та медицина"
    elif (
        mcc
        in (
            5733,
            5735,
            5941,
            7221,
            7333,
            7395,
            7929,
            7932,
            7933,
            7941,
            7991,
            7995,
            8664,
        )
        or mcc in range(5970, 5974)
        or mcc in range(5945, 5948)
        or mcc in range(5815, 5819)
        or mcc in range(7911, 7923)
        or mcc in range(7991, 7995)
        or mcc in range(7996, 8000)
    ):
        return "Розваги та спорт"
    elif mcc in range(5811, 5815):
        return "Кафе та ресторани"
    elif mcc in (
        5297,
        5298,
        5300,
        5311,
        5331,
        5399,
        5411,
        5412,
        5422,
        5441,
        5451,
        5462,
        5499,
        5715,
        5921,
    ):
        return "Продукти й супермаркети"
    elif mcc in (7829, 7832, 7841):
        return "Кіно"
    elif (
        mcc
        in (
            5172,
            5511,
            5541,
            5542,
            5983,
            7511,
            7523,
            7531,
            7534,
            7535,
            7538,
            7542,
            7549,
        )
        or mcc in range(5531, 5534)
    ):
        return "Авто та АЗС"
    elif mcc in (
        5131,
        5137,
        5139,
        5611,
        5621,
        5631,
        5641,
        5651,
        5655,
        5661,
        5681,
        5691,
        5697,
        5698,
        5699,
        5931,
        5948,
        5949,
        7251,
        7296,
    ):
        return "Одяг і взуття"
    elif mcc == 4121:
        return "Таксі"
    elif mcc in (742, 5995):
        return "Тварини"
    elif mcc in (2741, 5111, 5192, 5942, 5994):
        return "Книги"
    elif mcc in (5992, 5193):
        return "Квіти"
    elif mcc in (4814, 4812):
        return "Поповнення мобільного"
    elif mcc == 4829:
        return "Грошові перекази"
    elif mcc == 4900:
        return "Комунальні послуги"
    else:
        return "Інше"


def convert_dates(start_date: str = None, end_date: str = None):
    if not start_date:
        start_date = datetime.datetime.today().strftime("%d.%m.%Y") + " 00:00:01"
    elif len(start_date) < 11:
        start_date += " 00:00:01"

    if not end_date:
        end_date = datetime.datetime.today().strftime("%d.%m.%Y") + " 23:59:59"
    elif len(end_date) < 11:
        end_date += " 23:59:59"

    start_date_unix = int(
        time.mktime(
            datetime.datetime.strptime(
                start_date, "%d.%m.%Y %H:%M:%S"
            ).timetuple()
        )
    )
    end_date_unix = int(
        time.mktime(
            datetime.datetime.strptime(
                end_date, "%d.%m.%Y %H:%M:%S"
            ).timetuple()
        )
    )
    return start_date_unix, end_date_unix    


def convert_mono_to_pmts(mono_user: MonoUser, data: dict) -> dict:
    data_ = {}
    try:
        account = data["data"]["account"]
        id = data["data"]["statementItem"]["id"]
        rdate_mono = data["data"]["statementItem"]["time"]
        rdate = datetime.datetime.fromtimestamp(rdate_mono)
        dt = f"{rdate:%d.%m.%Y %H:%M:%S}"
        description = data["data"]["statementItem"]["description"].replace("'", "")
        mcc = data["data"]["statementItem"]["mcc"]
        amount = data["data"]["statementItem"]["amount"]
        # operationAmount = data["data"]["statementItem"]["operationAmount"]
        currencyCode = data["data"]["statementItem"]["currencyCode"]
        balance = data["data"]["statementItem"]["balance"]
        # hold = data["data"]["statementItem"]["hold"]
        if "comment" in data["data"]["statementItem"]:
            comment = data["data"]["statementItem"]["comment"].replace("'", "")
        else:
            comment = ""

    except Exception as err:
        current_app.logger.error(f'{err}')
        return data_

    user_id = 999999

    try:
        user_id = mono_user.user_id

        category_name = _mcc(mcc)

        is_deleted = 0
        category_id = None
        user_config = mono_user.user.config
        for config_row in user_config:
            # set as deleted according to rules
            if config_row.type_data == ConfigTypes.IS_DELETED_BY_DESCRIPTION.value:
                if description.find(config_row.value_data) > -1:
                    is_deleted = 1
            # for replace category according to rules
            if config_row.type_data == ConfigTypes.CATEGORY_REPLACE.value:
                if config_row.add_value and description.find(config_row.value_data) > -1:
                    try:
                        category_id, description = int(config_row.add_value), category_name
                        comment = description
                        break
                    except Exception as err:
                        mono_logger.warning('can not set category id for cat: {cat}, {err}')

        if not category_id:
            category_id = get_category_id(user_id, category_name)

        data_ = {
            'category_id': category_id, 'mydesc': comment,
            'amount': -1 * amount, 'currencyCode': currencyCode, 'mcc': mcc,
            'rdate': rdate, 'type_payment': 'card', 'bank_payment_id': id,
            'user_id': user_id, 'source': 'mono', 'account': account,
            'mono_user_id': mono_user.id, 'is_deleted': is_deleted,
             "category_name": category_name, "balance": balance,
        }
    except Exception as err:
        mono_logger.error(f'convert mono data to pmts failed. {err}')

    return data_


def get_mono_pmts(start_date: str = "", end_date: str = "", mono_user_id: int = None):

    result = []
    token = None
    accounts = []

    mono_user_info = get_mono_user_info__(mono_user_id)
    mono_user_token = get_mono_user_token(mono_user_id)
    accounts = mono_user_info.get('accounts')

    start_date_unix, end_date_unix = convert_dates(start_date, end_date)

    for account in accounts:
        if account.get('balance') < 1:
            continue
        
        url = f"""{mono_api_url}/personal/statement/{account.get('id')}/{start_date_unix}/{end_date_unix}"""
        header = {"X-Token": mono_user_token}

        r = requests.get(url, headers=header)

        err_cnn = 0
        while r.status_code != 200:
            err_cnn += 1
            time_to_sleep = 15 + random.randint(10, 40)
            current_app.logger.warning(
                f"""Status request code: {r.status_code}\nWait {time_to_sleep}s..."""
            )
            time.sleep(time_to_sleep)
            r = requests.get(url, headers=header)
            if err_cnn > 2:
                current_app.logger.error("Error connection more then 2")
                return result

        result.extend(r.json())
    
    if len(result) < 1:
        current_app.logger.info("No rows returned from Request..")

    return result


def process_mono_data_pmts(
        user_id: int,
        start_date: str = None,
        end_date: str = None,
        mono_user_id: str = None,
        mode: str = None
    ):

    result = []
    result_html = 'Data not found'
    total_in = 0
    total_out = 0
    if not mono_user_id:
        mono_users = get_mono_users_(user_id)
    else:
        mono_users = [{"id": mono_user_id}]
    for mono_user in mono_users:
        mono_pmts = get_mono_pmts(start_date, end_date, mono_user.get('id'))
        if not mono_pmts:
            return result_html
        
        result.append(
                """
    <table class="table table-bordered"><tr><th>Дата</th><th>Опис</th><th>Розділ</th><th>Сума</th></tr>"""
            )

        for item in mono_pmts:
            data = {}
            data['end_date_'] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item["time"]))
            data['id'] = item["id"]
            data['desc'] = item["description"]
            data['mcc'] = item["mcc"]
            data['cat'] = _mcc(item.get('mcc'))
            data['suma'] = -1 * item["amount"] / 100
            data['val'] = item["currencyCode"]
            data['bal'] = item["balance"]
            data['user'] = user_id

            if item["amount"] > 0:
                total_in += item["amount"]
            elif item["amount"] < 0:
                total_out += item["amount"]

            data['descnew'] = data['desc'].replace("\n", " ")
            mono_logger.info(f"{data}")

            if mode == "import":
                data_ = convert_mono_to_pmts(mono_user_id, data)
                add_new_mono_payment(data_)
        
            result.append(
                f"""<tr><td>{data['end_date_']} </td><td> {data['descnew']}</td><td> {data['cat']}</td><td> {data['suma']}</td></tr>"""
            )

        result.append("</table>")
        result.append(f'total in: {int(total_in / 100)}, totsl out: {int(total_out / 100)}')
        result_html = '\n'.join(result)

    return result_html


def get_user_id(account: str) -> int:
    user_id = 999999
    mono_account = db.session().query(Config).join(User).filter(
        Config.type_data == 'mono_account'
    ).filter(Config.value_data == account).one_or_none()

    if mono_account:
        user_id = mono_account.user_id
    return user_id 


def get_mono_user(mono_user_id: int) -> MonoUser:
    mono_user = db.session().query(MonoUser).get(mono_user_id)

    if mono_user:
        return mono_user
    return None 


def get_category_id(user_id: int, category_name: str) -> int:
    category = db.session().query(Category).filter(
        and_(
            Category.name.like(f'%{category_name}%'),
            Category.user_id == user_id,
            Category.parent_id == 0,
        )
    ).one_or_none()
    
    if category:
        category_id = category.id
    else:
        new_category = Category()
        new_category.from_dict({"name": cat, "parent_id": 0, "user_id": user_id})
        db.session().add(new_category)
        db.session().commit()
        category_id = new_category.id
    return category_id


def add_new_mono_payment(data) -> dict:
    result = None
    try:
        new_payment = Payment()
        new_payment.from_dict(**data)
        db.session().add(new_payment)
        db.session().commit()
        result = new_payment
    except Exception as err:
        db.session().rollback()
        db.session().flush()
        mono_logger.error(f'add new mono webhook FAILED:\n{err}')
    return result


def get_mono_user_token(mono_user_id: int) -> str:
    mono_user = db.session().query(MonoUser).get(mono_user_id)
    
    return mono_user.token
