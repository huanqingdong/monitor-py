#!/usr/bin/python
# -*- coding: utf-8 -*-


import urllib2, time, configparser
import json, datetime
import urllib3, requests

urllib3.disable_warnings()


class Stock:
    def __init__(self, code):
        self.code = code
        self.name = ''
        self.price = 0.0
        self.change_percent = 0


def load_config():
    config = configparser.ConfigParser()
    config.read('monitor.conf')
    global run_mode
    run_mode = str(config.get('config', 'run_mode'))

    global wechart_corp_id, wechart_corp_secret, wechart_agent_id, wechart_user_id, wechart_subject, \
        wechart_send_interval
    wechart_corp_id = str(config.get('config', 'wechart_corp_id'))
    wechart_corp_secret = str(config.get('config', 'wechart_corp_secret'))
    wechart_agent_id = str(config.get('config', 'wechart_agent_id'))
    wechart_user_id = str(config.get('config', 'wechart_user_id'))
    wechart_send_interval = int(config.get('config', 'wechart_send_interval'))

    global alert_rate, stock_code1, stock_code2, init_price1, init_price2, sleep_time, up_rate, down_rate
    alert_rate = float(config.get('config', 'alert_rate'))
    stock_code1 = str(config.get('config', 'stock_code1'))
    stock_code2 = str(config.get('config', 'stock_code2'))
    init_price1 = float(config.get('config', 'init_price1'))
    init_price2 = float(config.get('config', 'init_price2'))
    sleep_time = int(config.get('config', 'sleep_time'))
    init_rate = (init_price1 - init_price2) / (0.5 * (init_price1 + init_price2))
    up_rate = init_rate + alert_rate
    down_rate = init_rate - alert_rate
    stock_code1 = format_code(stock_code1)
    stock_code2 = format_code(stock_code2)

    # print 'reload_config'


def get_token(corp_id, corp_secret):
    url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
    data = {
        "corpid": corp_id,
        "corpsecret": corp_secret
    }
    r = requests.get(url=url, params=data, verify=False)
    token = r.json()['access_token']
    return token


def send_message(token, user, agent_id, subject, content):
    url = "https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=%s" % token
    data = {
        "touser": user,  # 企业号中的用户帐号，在zabbix用户Media中配置，如果配置不正常，将按部门发送。
        "msgtype": "text",  # 消息类型。
        "agentid": agent_id,  # 企业号中的应用id。
        "text": {
            "content": subject + '\n' + content
        },
        "safe": "0"
    }
    r = requests.post(url=url, data=json.dumps(data), verify=False)
    return r.json()


def log(msg):
    if run_mode == 'dev':
        if isinstance(msg, dict):
            print msg
        else:
            print get_now_str() + "===>" + msg


def get_now_str():
    time_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return time_str


def send_wechart_msg(subject):
    log('send wechart')
    token = get_token(wechart_corp_id, wechart_corp_secret)
    time_str = get_now_str()
    content = time_str
    status = send_message(token, wechart_user_id, wechart_agent_id, subject, content)
    log(status)
    if status['errcode'] == 0:
        time.sleep(wechart_send_interval)


def read_as_list(url):
    # print url
    result = {}
    response_str = urllib2.urlopen(url).read().decode('gbk')
    # print response_str
    row_list = response_str.split(';', response_str.count(';') - 1)
    for row in row_list:
        info_list = row.split('=')
        code = info_list[0].replace('var hq_str_', '').strip()
        stock = Stock(code)
        info_list1 = info_list[1].replace('"', '').split(',')
        # print info_list1
        stock.name = info_list1[0]
        stock.price = info_list1[1]
        stock.change_percent = info_list1[3]
        result[code] = stock
    return result


def format_code(code):
    if code.startswith("3") or code.startswith("0"):
        return "s_sz" + code
    if code.startswith("6") or code.startswith("7"):
        return "s_sh" + code
    return code


load_config()

while True:
    try:
        result_map = read_as_list("http://hq.sinajs.cn/rn=1&list=" + stock_code1 + "," + stock_code2)
        stock_1 = result_map[stock_code1]
        stock_2 = result_map[stock_code2]
        if stock_1.price <= 0:
            log(stock_1.code + "<0")
        elif stock_2.price <= 0:
            log(stock_2.code + "<0")
        else:
            price1 = float(stock_1.price)
            price2 = float(stock_2.price)
            if price1 > 0 and price2 > 0:
                if price2 / price1 > 5:
                    price2 = price2 / 10
                if price1 / price2 > 5:
                    price2 = price2 * 10
                #  dif_up s1b2
                up_cal_val2 = (price1 - price1 / 2 * up_rate) / (1 + 0.5 * up_rate)
                # dif_down s2b1
                down_cal_val2 = (price1 - price1 / 2 * down_rate) / (1 + 0.5 * down_rate)
                log('p1:' + str(price1) + ",p2:" + str(price2) + ',up:' + str(round(up_cal_val2, 3)) + ',down:' + str(
                    round(down_cal_val2, 3)))

                if price2 < up_cal_val2:
                    wechart_subject = 's-' + stock_1.code
                    log(wechart_subject)
                    send_wechart_msg(wechart_subject)
                elif price2 > down_cal_val2:
                    wechart_subject = 's-' + stock_1.code
                    log(wechart_subject)
                    send_wechart_msg(wechart_subject)
            else:
                log('p1:' + str(price1) + ",p2:" + str(price2))
        time.sleep(sleep_time)
        load_config()
    except TypeError:
        log('TypeError')
    else:
        log('其他异常')
