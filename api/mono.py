# _*_ coding:UTF-8 _*_
import logging
import requests
import time

from flask import Blueprint, request, abort, current_app
from flask_cors import cross_origin
from flask_jwt_extended import jwt_required

from utils import do_sql_cmd
from config import cfg, users, mono_api_url, mono_webhook
from func import send_telegram
from api.mono_funcs import _mcc


mono_bp = Blueprint(
    "mono_bp",
    __name__,
)

mono_logger = logging.getLogger('mono')


@mono_bp.route("/api/mono/webhook/<user>", methods=["GET"])
@cross_origin()
@jwt_required()
def get_webhook(user):
    """
    set a new webhook on mono
    """
    token = None
    result = {}

    if not user:
        current_app.logger.error('Not valid data')
        abort(402, 'Not valid data')        

    for user_ in users:
        if user_.get('name') == user:
            token = user_.get("token")
            break
    
    if not token:
        current_app.logger.error(f'Token not found: {user}')
        abort(401, f'Token not found: {user}')

    header = {"X-Token": token}

    url = f"{mono_api_url}/personal/client-info"

    try:
        r = requests.get(url, headers=header)
    except Exception as err:
        current_app.logger.error(f"{err}")
        abort(400, f'Bad request: {err}\n{r.text}')

    result = r.json()
    result['this_api_webhook'] = request.host_url + 'api/mono/webhook'
    result['user'] = user

    return result


@mono_bp.route("/api/mono/webhook", methods=["PUT"])
@cross_origin()
@jwt_required()
def set_webhook():
    """
    set a new webhook on mono
    """
    token = None

    try: 
        data = request.get_json()
        user = data['user']
        webhook = data.get('webhook', mono_webhook)
    except Exception as err:
        current_app.logger.error(f"{err}")
        abort(400, f'Not valid data: {err}')

    url = f"""{mono_api_url}/personal/webhook"""

    for user_ in users:
        if user_.get('name') == user:
            token = user_.get("token")
            break
    if not token:
        abort(401, f'Token not found: {user}')

    header = {"X-Token": token}
    data = {"webHookUrl": webhook}

    try:
        r = requests.post(url, json=data, headers=header)
    except Exception as err:
        current_app.logger.error(f"{err}")
        abort(400, f'Bad request: {err}\n{r.text}')

    return {"status_code": r.status_code, "data": r.text}


@mono_bp.route("/api/mono/webhook", methods=["POST", "GET"])
@cross_origin()
def new_mono_webhook():
    """
    insert a new webhook from mono
    input: rdate,cat,sub_cat,mydesc,suma
    """

    if request.method == 'GET':
        return {'status': 'ok'}

    try:
        data = request.get_json()

        mono_logger.info(f'\n{data}\n')
 
        account = data["data"]["account"]
        id = data["data"]["statementItem"]["id"]
        rdate_mono = data["data"]["statementItem"]["time"]
        dt = time.strftime("%d.%m.%Y %H:%M:%S", time.localtime(rdate_mono))
        t2mysql = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(rdate_mono))
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
        abort(422, "Not valid data")

    user = None

    try:
        suma = round(amount / 100, 2)
        # coment = f"\ncomment: {comment}"
        for user_ in users:
            if account in user_["account"]:
                user = user_.get('name')
                break

        if not user:
            user = "unknown"

        cat = _mcc(mcc)
        msg = []
        msg.append(
            f"""<b>{cat}</b>
    user: {user}
    time: {dt}
    description: {description} {comment}
    mcc: {mcc}
    amount: {suma}
    currencyCode: {currencyCode}
    balance: {balance}
    """
        )

        deleted = 0
        name_rozhid = ""
        for dlt in cfg["isDeleted"]:
            if description.find(dlt[0]) > -1:
                deleted = 1
                name_rozhid = dlt[1]
                break

        for cat1 in cfg["Category"]:
            if len(cat1) > 2 and description.find(cat1[2]) > -1:
                cat = cat1[0]
                comment = description
                description = cat1[1]
                break

        data_ = {
            'cat': cat, 'sub_cat': description, 'mydesc': comment,
            'suma': -1 * suma, 'currencyCode': currencyCode, 'mcc': mcc,
            'rdate': t2mysql, 'type_payment': 'CARD', 'id_bank': id,
            'owner': user, 'source': 'mono', 'deleted': deleted
        }

        if suma < 0:
            sql = """INSERT IGNORE INTO `myBudj` 
(`cat`, `sub_cat`, `mydesc`, `suma`, `currencyCode`, `mcc`, 
`rdate`, `type_payment`, `id_bank`, `owner`, `source`, `deleted`) 
VALUES 
(:cat, :sub_cat, :mydesc, :suma, :currencyCode, :mcc, :rdate,
 'CARD', :id_bank, :owner, :source, :deleted)
"""

            res = do_sql_cmd(sql, data_)

            if res["rowcount"] < 1:
                msg.append(f"\nerror. [{res}]\n{sql}")
            else:
                msg.append(f"\ninsert to myBudj Ok. [{res}]")

        send_telegram("".join(msg), "HTML", "", "bank")
        return {"status": "ok"}
    except Exception as err:
        current_app.logger.error(f'{err}')
        abort(500, str(err))
