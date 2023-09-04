from flask import Flask, render_template, send_file, request, redirect, Markup, url_for, abort, jsonify
from datetime import datetime
import datetime as dt
import pandas as pd
import os
import yfinance as yf
import numpy as np
import plotly.io as pio
import plotly.express as px
import sqlite3
import py_vollib.black_scholes.greeks.analytical as pyv

app = Flask(__name__, static_folder='static')


connection=sqlite3.connect('db/options.db', check_same_thread=False)
c=connection.cursor()

## SECURITY ##
'''ipDict = {'103': ['103.21.244.0/22', '103.22.200.0/22', '103.31.4.0/22'],
'104': ['104.16.0.0/13', '104.24.0.0/14'],
'108': ['108.162.192.0/18'],
'131': ['131.0.72.0/22'],
'141': ['141.101.64.0/18'],
'162': ['162.158.0.0/15'],
'172': ['172.64.0.0/13'],
'173': ['173.245.48.0/20'],
'188': ['188.114.96.0/20'],
'190': ['190.93.240.0/20'],
'197': ['197.234.240.0/22'],
'198': ['198.41.128.0/17']}

@app.before_request
def limit_remote_addr():
    client_ip = str(request.remote_addr)
    isValid = False
    try:
        ipRanges = ipDict[client_ip.split('.')[0]]
        for ipRange in ipRanges:
            if ipaddress.IPv4Address(client_ip) in ipaddress.IPv4Network(ipRange):
                isValid = True
                break
        if not isValid:
            abort(403)
    except Exception as e:
        abort(403)'''
## SECURITY ##

##graph related stuff##

typesDict = {"lastPrice":"Last price",
             "volume":"Volume",
             "openInterest":"Open Interest",
             "impliedVolatility":"Implied Volatility"
        }

def getWeekdays(startDate, endDate):
    startDateDt = dt.datetime.strptime(startDate, "%Y-%m-%d")
    endDateDt = dt.datetime.strptime(endDate, "%Y-%m-%d")

    days = 0
    while startDateDt <= endDateDt:
        if not startDateDt.weekday() in [5, 6]:
            days +=  1
        startDateDt += dt.timedelta(days=1)

    return days

def graphOptionImg(ticker, strike, exp, type_, startDate, endDate, graphType):
    print("graph function")
    ticker = ticker.upper()
    ticker = ticker.strip()
    limit = 30
    offset = 0
    modif = ''

    try:
        startDateDt = dt.datetime.strptime(startDate, "%Y-%m-%d")
    except:
        startDateDt = ''
    try:
        endDateDt = dt.datetime.strptime(endDate, "%Y-%m-%d")
    except:
        endDateDt = ''

    todayDt = dt.datetime.now()
    today = todayDt.strftime("%Y-%m-%d")
    if len(endDate) == 0:
        endDate = dt.date.today().strftime('%Y-%m-%d')
        if len(startDate) != 0:
            if startDateDt > todayDt:
                return '', 'Your start date is in the future. Please choose a different start date.'
            limit = getWeekdays(startDate, endDate)

    else:
        if endDate and startDate:
            if endDateDt < startDateDt:
                temp = endDate
                tempDt = endDateDt
                endDate = startDate
                endDateDt = startDateDt
                startDate = temp
                startDateDt = tempDt

            if startDateDt > todayDt:
                return '', 'Your start date is in the future. Please choose a different start date.'

            if endDateDt > todayDt:
                endDate = today

            offset = getWeekdays(endDate, today)-1
            limit = getWeekdays(startDate, endDate)
            if not os.path.exists(f'../../option_data/logs/{today}.txt') and offset > 0:
                offset -= 1



    dispType = typesDict[graphType]

    if type_ == 'call':
        type_ = 'C'
        typeName = 'Calls'
    else:
        type_ = 'P'
        typeName = 'Puts'
    #initialize arrays
    valueArray = []
    dateArray = []
    print("fetching db")
    dataList = c.execute(f'''
        SELECT date, {graphType} FROM options
        WHERE ticker="{ticker}" AND strike="{strike}" AND exp="{exp}" AND type="{type_}"
        ORDER BY date DESC
        LIMIT {limit} OFFSET {offset};
    ''').fetchall()

    if not dataList:
        return '', 'We seem to not have data for your request... Make sure the parameters you have entered are correct, and that the start and end dates are not equal. If you think this is a mistake, please email us at dev@jcrayb.com'
    for data in dataList:
        dateArray += [data[0]]
        valueArray += [data[1]]

    if graphType == 'lastPrice':
        modif = '$'
    print("generating graph")
    #create and configure graph
    graph = pd.DataFrame()
    graph['Date'] = dateArray
    graph[dispType] = valueArray
    graph = graph.set_index('Date')
    plot = px.line(graph,render_mode='svg')
    plot.update_layout(
        title=f"{ticker} {exp} {strike}$ {typeName} {dispType}",
        xaxis_title="Date",
        showlegend = False,
        margin = {'r':0, 'l': 0},
        yaxis_visible=False
    )
    plot.update_traces(
        hovertemplate =
        f'<i>{dispType}</i>:' + modif+'%{y:.2f}'+
        '<br><b>Date:</b>: %{x}<br>'
    )
    #make a unique path for each ticker
    chart = pio.to_json(plot)
    return chart, 'none'



def returnStrikes(ticker, date, exp):
    strikesList = None
    #check if the ticker has data
    if os.path.exists(f'../../option_data/csvs/{ticker}/{date}/{expiry} C.csv'):
        df = pd.read_csv(f'../../option_data/csvs/{ticker}/{date}/{expiry} C.csv')
        strikesList = df['strike']
    elif os.path.exists(f'../../option_data/csvs/{ticker}/{date}/{expiry} P.csv'):
        df = pd.read_csv(f'../../option_data/csvs/{ticker}/{date}/{expiry} P.csv')
        strikesList = df['strike']
    return strikesList

def returnExpirations(ticker):
    expList = None
    #check if the ticker has data
    if not os.path.exists(f'../../option_data/csvs/{ticker}'):
        print(f'No option data could be found for {ticker}')
    else:
        expList = []
        #if it does take date of last generated data
        recentData = os.listdir(f'../../option_data/csvs/{ticker}')[-1]
        files = os.listdir(f'../../option_data/csvs/{ticker}/{recentData}')

        for file in files:
            date = file.split(' ')[0]
            if not date in expList:
                expList += [date]
        print(date)
        #get the list of strikes from that day's data file
    return expList

def getGreeks(date, expiry, stockPrice, r, sigma, strike, optionType):
    flag = optionType.lower()
    dateDt = dt.datetime.strptime(date, "%Y-%m-%d")
    expiryDt = dt.datetime.strptime(expiry, "%Y-%m-%d")

    t = (expiryDt-dateDt).days/365.25

    delta = pyv.delta(flag, stockPrice, strike, t, r, sigma)
    gamma = pyv.gamma(flag, stockPrice, strike, t, r, sigma)
    theta = pyv.theta(flag, stockPrice, strike, t, r, sigma)
    vega = pyv.vega(flag, stockPrice, strike, t, r, sigma)
    rho  = pyv.rho(flag, stockPrice, strike, t, r, sigma)
    return delta, gamma, vega, theta, rho

def verifyInput(args):
    ticker = args['ticker']
    exp_date = args['exp_date']
    start_date = args['start_date']
    end_date = args['end_date']
    strike_price = args['strike_price']
    put_or_call = args['put_or_call']
    exp_date_dt = dt.datetime.strptime(exp_date, '%Y-%m-%d')

    if not exp_date_dt.weekday() == 4:
        return 'The expiration date you have entered is not a friday. Make sure you have entered a correct date.'

    if yf.Ticker(ticker).history().empty:
        return 'The symbol you have entered is invalid. Make sure you have entered a correct symbol.'

    if not exp_date:
        return 'Please provide an expiry date.'

    if not strike_price:
        return 'Please provide a strike price.'

    if start_date == end_date and start_date and end_date:
        return 'Your start and end dates are identical. Please choose a different range.'

    return ''

def index(type_, args):
    ticker = args['ticker']
    exp_date = args['exp_date']
    start_date = args['start_date']
    end_date = args['end_date']
    strike_price = float(args['strike_price'])
    put_or_call = args['put_or_call']
    exp_date_dt = dt.datetime.strptime(exp_date, '%Y-%m-%d')
    error = verifyInput(args)

    if error:
        return '', error

    graph, error = graphOptionImg(ticker, strike_price, exp_date, put_or_call, start_date, end_date, type_)
    '''except Exception as e:
        print(e)
        graph = e'''
    return graph, error

def graphGreeks(args):
    args = request.args
    ticker = args['ticker']
    exp_date = args['exp_date']
    start_date = args['start_date']
    end_date = args['end_date']
    strike_price = float(args['strike_price'])
    put_or_call = args['put_or_call']
    exp_date_dt = dt.datetime.strptime(exp_date, '%Y-%m-%d')

    error = verifyInput(args)
    if error:
        return '', error

    startDate = start_date
    endDate = end_date

    ticker = ticker.upper()
    ticker = ticker.strip()
    limit = 30
    offset = 0
    modif = ''

    try:
        startDateDt = dt.datetime.strptime(startDate, "%Y-%m-%d")
    except:
        startDateDt = ''
    try:
        endDateDt = dt.datetime.strptime(endDate, "%Y-%m-%d")
    except:
        endDateDt = ''

    todayDt = dt.datetime.now()
    today = todayDt.strftime("%Y-%m-%d")
    if len(endDate) == 0:
        endDate = dt.date.today().strftime('%Y-%m-%d')
        if len(startDate) != 0:
            if startDateDt > todayDt:
                return '', 'Your start date is in the future. Please choose a different start date.'
            limit = getWeekdays(startDate, endDate)

    else:
        if endDate and startDate:
            if endDateDt < startDateDt:
                temp = endDate
                tempDt = endDateDt
                endDate = startDate
                endDateDt = startDateDt
                startDate = temp
                startDateDt = tempDt

            if startDateDt > todayDt:
                return '', 'Your start date is in the future. Please choose a different start date.'

            if endDateDt > todayDt:
                endDate = today

            offset = getWeekdays(endDate, today)-1
            limit = getWeekdays(startDate, endDate)
            if not os.path.exists(f'../../option_data/logs/{today}.txt') and offset > 0:
                offset -= 1

    if put_or_call == 'call':
        type_ = 'C'
        typeName = 'Calls'
    else:
        type_ = 'P'
        typeName = 'Puts'
    #initialize arrays
    valueArray = []
    dateArray = []

    dataList = c.execute(f'''
        SELECT date, impliedVolatility FROM options
        WHERE ticker="{ticker}" AND strike="{strike_price}" AND exp="{exp_date}" AND type="{type_}"
        ORDER BY date DESC
        LIMIT {limit} OFFSET {offset};
    ''').fetchall()

    if not dataList:
        return '', 'We seem to not have data for your request... Make sure the parameters you have entered are correct, and that the start and end dates are not equal. If you think this is a mistake, please email us at dev@jcrayb.com'

    hist = yf.Ticker(ticker).history(start=startDate)['Close']
    deltaArray = []
    gammaArray = []
    vegaArray = []
    thetaArray = []
    rhoArray = []
    dateArray = []
    for data in dataList:
        date = data[0]
        try:
            r = yf.Ticker('^IRX').history(start=startDate)['Close'][date]/100
            stockPrice = hist[date]
            dateArray += [date]
        except:
            continue
        sigma = data[1]
        delta, gamma, vega, theta, rho = getGreeks(date, exp_date, stockPrice, r, sigma, strike_price, type_)
        deltaArray += [delta]
        gammaArray += [gamma]
        vegaArray += [vega]
        thetaArray += [theta]
        rhoArray += [rho]

    graph = pd.DataFrame()
    graph['Date'] = dateArray
    graph['Delta'] = deltaArray
    graph['Gamma'] = gammaArray
    graph['Vega'] = vegaArray
    graph['Theta'] = thetaArray
    graph['Rho'] = rhoArray
    graph = graph.set_index('Date')
    plot = px.line(graph,render_mode='svg')
    plot.update_layout(
        title=f"{ticker} {exp_date} {strike_price}$ {typeName} greeks",
        xaxis_title="Date",
        showlegend = True,
        margin = {'r':0, 'l': 0},
        yaxis_visible=False
    )
    chart = pio.to_json(plot)
    return chart, 'none'

@app.route('/graph/single/', defaults={'type_':''}, methods=['GET'])
@app.route('/graph/single/<type_>', methods=['GET', 'POST'])
def singlePrice(type_):
    print("received request")
    if not type_:
        return render_template('single/graph.html')
    args = request.args
    print("treating request")
    graph, error = index(type_, args)
    print("returning graph")
    return {'message': graph , 'error':error}



@app.route('/graph/single/greeks', methods=['GET'])
def singleGreeks():
    args = request.args
    graph, error = graphGreeks(args)
    return {'message':graph, 'error':error}
##Graph related stuff##

@app.route('/healthcheck', methods=['GET'])
def healthcheck():
    return {'status':'healthy'}

if __name__ == '__main__':
    app.run(host="0.0.0.0", port="8080")
