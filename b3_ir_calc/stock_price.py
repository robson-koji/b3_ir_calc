# coding: utf-8

import argparse, bs4, json, requests
from urllib2 import urlopen
from bs4 import BeautifulSoup
from collections import defaultdict
from datetime import datetime, date

from ir_calc import ObjectifyData


def get_socks(mkt_type, file, path):
    """
    Open a CSV file (source of operations at the broker)
    Make use of ir_calc.py ObjectifyData class.
    """
    b3_tax_obj = ObjectifyData(mkt_type, file, path)
    csv = b3_tax_obj.file2object(csv_only=True)

    stocks = set()
    for line in csv:
        line_dict = b3_tax_obj.read_line(line)
        if line_dict:
            stocks.add(line_dict['stock'])

    return stocks


def get_price(stock):
    """ Get stock prices on Yahoo Finance """

    url = 'https://finance.yahoo.com/quote/%s.sa' % (stock)
    try:
        page = urlopen(url)
    except:
        print('Error opening the URL')

    soup = bs4.BeautifulSoup(page,'html.parser')
    price = soup.find('div',{'class': 'My(6px) Pos(r) smartphone_Mt(6px)'}).find('span').text
    hour = soup.find('div',{'class': 'My(6px) Pos(r) smartphone_Mt(6px)'}).findAll('span')[-1].text

    return (price, hour)


def save_json(stock_price):
    """ Save stock price to a JSON file """
    now = datetime.now().date()
    dict_json = {str(now): stock_price}
    with open('files/stock_price.json', 'w') as fp:
        json.dump(dict_json, fp)


if __name__ == "__main__":
    """
    To get stock prices from your CSV file, call this script wiht arguments.
    python stock_price.py --path --file
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--mkt_type', default='VIS')
    parser.add_argument('--path', default='test_sample')
    parser.add_argument('--file', default='sample.csv')
    args = parser.parse_args()

    stocks = get_socks(mkt_type=args.mkt_type, path=args.path, file=    args.file)
    stock_price = defaultdict()
    for stock in stocks:
        try:
            (price, hour) = get_price(stock)
            stock_price[stock] = {'price': price, 'hour': hour}
        except:
            pass
    save_json(stock_price)
