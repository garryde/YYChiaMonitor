import sys
import requests
import json
import os
import configparser
from datetime import datetime
import telegram
import time

#初始化配置文件
file = 'config.ini'
if not os.path.exists(file):
    con = configparser.ConfigParser()
    con.add_section('chiayy')
    con.set('chiayy', 'user_token', '')
    con.add_section('telegram')
    con.set('telegram', 'personal_chat_id', '')
    con.set('telegram', 'offical_channel_id', '')
    con.set('telegram', 'test_channel_id', '')
    con.set('telegram', 'bot_token', '')
    con.add_section('status')
    con.set('status', 'is_test', 'False')
    with open(file, 'w') as fw:
        con.write(fw)
    print('已生成配置文件！程序退出！')
    sys.exit()
#加载配置文件
con = configparser.ConfigParser()
con.read(file, encoding='utf-8')
user_token = dict(con.items('chiayy'))['user_token']
personal_chat_id = dict(con.items('telegram'))['personal_chat_id']
offical_channel_id = dict(con.items('telegram'))['offical_channel_id']
test_channel_id = dict(con.items('telegram'))['test_channel_id']
bot_token = dict(con.items('telegram'))['bot_token']
is_test = True if dict(con.items('status'))['is_test'].lower() == 'true' else False

#变量定义
getStatus = "https://openapi.wtt.fun:50433/web/farming/tool/getHarvesterSummary"
getHealth = "https://openapi.wtt.fun:50433/web/machine/get24HourHealthInfo"
getIncome = "https://openapi.wtt.fun:50433/web/account/getMiningIncomeInfo"

requestHeaderName = "x-chiayy-session-signed"
requestHeaderKey = user_token
requestBody = '{}'

bot = telegram.Bot(token=bot_token)

last_update_structure = {"isOnline":False,"space":0,"healthOf24hStr":"00","today":"00"}

isSecondaryCheckSpace = False

#休眠分钟数
interval = 15

#发送频道
chat_id = offical_channel_id
if is_test:
    chat_id= test_channel_id

# Telegram频道消息
def sendChannelMessage(message):
    try:
        bot.send_message(chat_id=chat_id, text=message, parse_mode=telegram.ParseMode.HTML)
        global err
        err = 0
    except Exception as e:
        print(e)
        time.sleep(30)
        sendPersonalMessage("#ChiaMonitor Telegram频道文本消息异常！")

# Telegram个人消息
def sendPersonalMessage(message, error = False):
    try:
        if error:
            global err
            err += 1
            print(err)
            if err <= error_time: return
            if err > 10:
                bot.send_message(personal_chat_id, "#ChiaMonitor 异常超过10次！", disable_notification=True)
        bot.send_message(personal_chat_id, message, disable_notification=True)
    except:
        time.sleep(interval * 60 * 5)
#获取API数据
def fetch_data(url):
    req = requests.post(url,headers= {requestHeaderName:requestHeaderKey},data = requestBody)  # 请求url（GET请求）
    return json.loads(req.text)
#income deal
def setIncomeFomat(income):
    return str(round(float(income),4))

# 持久化本地数据
def writeLocalData(listWrite):
    fileObject = open('ChiaMonitor.txt', 'w')
    fileObject.write(json.dumps(listWrite))
    fileObject.write('\n')

# 读取本地持久化数据
def readLocalData():
    listRead = last_update_structure
    rs = os.path.exists('ChiaMonitor.txt')
    if rs:
        file_handler = open('ChiaMonitor.txt', 'r')
        contents = file_handler.readlines()
        for i in contents:
            i = i.strip('\n')
            listRead = json.loads(i)
    else:
        writeLocalData(listRead)
    return listRead

# 读取持久化数据
last_update = readLocalData()
if is_test:
  last_update = last_update_structure

while True:
    ##########################矿机状态##########################
    #获取数据——处理网络失败异常
    try:
        current_status = fetch_data(getStatus)
    except Exception as e:
        time.sleep(60)
        sendPersonalMessage("#ChiaMonitor 网络请求异常！")
        print("网络请求异常")
        print(e)
        print()
        continue
    #解析结果-——处理key错误异常
    try:
        current_status = current_status['result'][0]
    except Exception as e:
        sendPersonalMessage("#ChiaMonitor Status解析错误！")
        print("Status解析错误")
        print(e)
        sendPersonalMessage("#ChiaMonitor\n"+current_status['errcode']+":"+current_status['message']+"\n系统已退出")
        print(current_status['message'])
        print()
        sys.exit()
    #解析数据
    isOnline = current_status['isOnline']
    dateLastOnline = str(datetime.fromtimestamp(current_status["dateLastOnline"]/1000))[0:19]

    space = current_status['space']
    fileSize = round(current_status["fileSize"]/1024/1024/1024/1024,2)

    #判断数据一致性，发送通知
    if isOnline != last_update.get('isOnline'):
        sendChannelMessage("#矿机状态变化提醒\n当前状态："+ ("在线" if isOnline else "离线") + "\n上次在线："+dateLastOnline)
        last_update['isOnline'] = isOnline

    if space != last_update.get('space'):
        #算力异常二次校验
        if space < last_update.get('space')/2:
            print("算力异常：当前算力："+space+"之前算力："+last_update.get('space'))
            if isSecondaryCheckSpace:
                #关闭二次校验标记，发送消息
                isSecondaryCheckSpace = False
            else:
                # 进入二次校验
                time.sleep(60)
                isSecondaryCheckSpace = True
                continue
        sendChannelMessage("#算力变化提醒\n在线算力："+str(fileSize)+"TB\n有效农田："+str(space))
        last_update['space'] = space

   ##########################健康度##########################
    try:
        current_health = fetch_data(getHealth)
    except Exception as e:
        time.sleep(60)
        sendPersonalMessage("#ChiaMonitor 网络请求异常！")
        print("网络请求异常")
        print(e)
        print()
        continue
    #解析结果-——处理key错误异常
    try:
        healthOf24hStr = str(current_health['result']['healthOf24hStr'])
    except Exception as e:
        sendPersonalMessage("#ChiaMonitor health解析错误！\n当前Json：" + current_health)
        print("health解析错误")
        print(e)
        print()
    #判断数据一致性，发送通知
    if healthOf24hStr[1] != last_update['healthOf24hStr'][1]:
        if isOnline:
            sendChannelMessage("#健康度变化提醒\n当前健康度："+healthOf24hStr)
            last_update['healthOf24hStr'] = healthOf24hStr

   ##########################收入##########################
    try:
        current_income = fetch_data(getIncome)
    except Exception as e:
        time.sleep(60)
        sendPersonalMessage("#ChiaMonitor 网络请求异常！")
        print("网络请求异常")
        print(e)
        print()
        continue
    #解析结果-——处理key错误异常
    try:
        current_income = current_income['result']
    except Exception as e:
        sendPersonalMessage("#ChiaMonitor income解析错误！\n当前Json：" + current_health)
        print("income解析错误")
        print(e)
        print()
    #解析数据
    today = setIncomeFomat(current_income['yesterday'])
    yesterday = setIncomeFomat(current_income['daysOf14'][1]['amountStr'])
    thisWeek = setIncomeFomat(current_income['thisWeek'])
    lastWeek = setIncomeFomat(current_income['lastWeek'])
    #判断数据一致性，发送通知
    if today != last_update.get('today'):
        sendChannelMessage("#收益变化提醒\n今日收益："+today+"\n昨日收益："+yesterday+"\n本周收益："+thisWeek+"\n上周收益："+lastWeek)
        last_update['today'] = today

    if not is_test:
        writeLocalData(last_update)
    time.sleep(interval * 60)