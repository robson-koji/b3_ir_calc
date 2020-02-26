# coding: utf-8

import csv
import copy
from decimal import *
from datetime import datetime, timedelta, date
from collections import defaultdict


class b3Tax():
    def __init__(self, corretora):
        self.corretora = corretora
        self.mm = monthsGroup()
        self.stocks = {}

    def two_digits_month(self, month):
        """ four digits year plus two digits months for all keys, allows order keys """
        if month < 10:
            month = "0%d" % (month)
        return month

    def subtract_one_month(self, month):
        """ receives current month, returns the key of previous active month """
        try:
            months = self.mm
            month_index = months.keys().index(month)
            if month_index:
                return months.keys()[month_index - 1]
            return None
        except:
            raise

    def read_line(self, line):
        # line = [10/07/2019,1-Bovespa,C,VIS,TAEE11 UNT N2,,100,"28,69",2869,D]
        line_dict = {}
        try:
            dt = datetime.strptime(line[0], '%d/%m/%Y')
            month = self.two_digits_month(dt.month)
            year_month_id = "%d%s" % (int(dt.year), month)
            year_month_id = int(year_month_id)
            stock = line[4].split()[0]
            qt = int(line[6])
            unit_price = Decimal(line[7].replace(',', '.').replace('"', ''))
            unit_price = round(unit_price, 2)
            value = Decimal(line[8].replace(',', '.').replace('"', ''))
            value = round(value, 2)
            buy_sell = line[2]

            line_dict = {'year_month_id':year_month_id,
                            'dt':dt,
                            'stock':stock,
                            'value':value,
                            'qt':qt,
                            'unit_price': unit_price,
                            'buy_sell': buy_sell,
                            }
            # import pdb; pdb.set_trace()
            return line_dict
        except Exception as e:
            print e
            raise

    def objectify_months(self, line, stock_updated_instance):
        #line_dict = {'year_month_id':year_month_id, 'dt':dt, 'stock':stock, 'value':value, 'buy_sell': buy_sell }
        month = self.mm[line['year_month_id']]
        month['dt'] = line['dt']

        if (line['buy_sell'] == 'C'):
            month['month_buy'] += line['value']
        elif (line['buy_sell'] == 'V'):
            month['month_sell'] += line['value']
        if stock_updated_instance is not None:
            month['operations'].append(stock_updated_instance)



    def objectify_stock(self, line):
        """
        Receives a csv line in dict format and create a stock object.
        Each stock object instance is a stock.
        For each line, create/update the object which returns the object __dict__
        """
        # Create or get instance of a stock account
        # It is populating self.stocks, a still not used dict.
        stock = self.stocks.setdefault(line['stock'], stockCheckingAccount(line['stock']))

        # Set operation attributes
        stock.start_operation(**line)

        # Calculate and set instance values
        if line['buy_sell'] == 'C':
            stock.buy(**line)
        if line['buy_sell'] == 'V':
            stock.sell(**line)

        # deep copy operation values
        cp_stock = copy.deepcopy(stock.__dict__)
        return cp_stock


    def file2object(self):
        """
        Process file line by line using the file's returned iterator
        to permit working with large files.
        Build months object and stocks objects.
        """
        try:
            file_path = 'files/%s.csv' % (self.corretora)
            with open(file_path) as file_handler:
                csv_reader = csv.reader(file_handler, quotechar='"', delimiter=',')
                next(csv_reader, None)
                csv_reader = reversed(list(csv_reader))

                while True:
                    try:
                        line = next(csv_reader)
                        line = self.read_line(line)

                        # if not 'KLBN11' in line['stock']:
                        #     continue
                        stock_updated_instance = self.objectify_stock(line)
                        self.objectify_months(line, stock_updated_instance)
                    except Exception as e:
                        raise
        except (IOError, OSError):
            print("Error opening / processing file")
        except StopIteration:
            pass
        #return self.mm

    def cumulate_loss(self, this_month):
        months = self.mm
        previous_month = self.subtract_one_month(this_month)
        months[this_month]['cumulate_loss'] = months[this_month]['month_loss']
        if previous_month:
            months[this_month]['cumulate_loss'] += months[previous_month]['cumulate_loss']

    def threshold_exempt(self, current_month):
        """
        When the total amount sold on one month is less than R$20,000.00
        no tax are applied over gain
        """
        if current_month['month_sell'] > 20000:
            return True
        return False


    def tax_calc(self, month, final_balance):
        month['tax'] = {'final_balance':final_balance,
                            'tax_amount': final_balance * 0.15}


    def month_add_detail(self):
        """
        Add gain, loss for months.
        Calculate final balance and due tax.
        """
        months = self.mm
        for month in months.keys():
            print "\n\n"
            print month

            balance_current_month = 0
            # if months[month]['month_sell'] > 20000:
            print "%s Total vendas : %s" % (month, months[month]['month_sell'])
            for operation in months[month]['operations']:
                if operation['buy_sell'] == 'V':
                    if operation['profit']:
                        balance_current_month += operation['profit']
                    elif operation['loss']:
                        balance_current_month -= operation['loss']

                print operation
            if balance_current_month > 0:
                months[month]['month_gain'] =  balance_current_month
            elif balance_current_month < 0:
                months[month]['month_loss'] =  balance_current_month

            self.cumulate_loss(month)

            if self.threshold_exempt(months[month]):
                if balance_current_month > 0:
                    final_balance = balance_current_month + months[month]['cumulate_loss']
                    if final_balance > 0:
                        months[month]['cumulate_loss'] = 0
                        self.tax_calc(months[month], final_balance)
                    elif final_balance <= 0:
                        months[month]['cumulate_loss'] = final_balance

            print balance_current_month
            print months[month]['month_gain']
            print months[month]['month_loss']
            print months[month]['cumulate_loss']
            print months[month]['tax']



class stockCheckingAccount():
    def __init__(self, name):
        self.name = name
        self.qt_total = 0
        self._avg_price = 0

    @property
    def avg_price(self):
        return self._avg_price

    @avg_price.setter
    def avg_price(self, new_avg_price):
        self._avg_price = new_avg_price

    def new_avg_price(self, qt, unit_price):
        current_position = self.qt_total * self.avg_price
        new_dock = qt * unit_price
        new_avg_price = (current_position + new_dock) / (self.qt_total + qt)
        self.avg_price = new_avg_price

    def profit_loss(self, qt, unit_price):
        if unit_price <= self.avg_price:
            self.loss += (qt * self.avg_price) - (qt * unit_price)
        elif unit_price >= self.avg_price:
            self.profit += (qt * unit_price) - (qt * self.avg_price)

    def start_operation(self, **kwargs):
        # Pass all csv line values to stockCheckingAccount instance
        self.__dict__.update(kwargs)
        # Init profit and loss for this operation
        # Will calculate this based on the avg_price * sell price.
        self.profit = 0
        self.loss = 0

    def buy(self, **line):
        self.new_avg_price(line['qt'], line['unit_price'])
        self.qt_total += line['qt']

    def sell(self, **line):
        self.profit_loss(line['qt'], line['unit_price'])
        if line['qt'] > self.qt_total:
            # Sometimes changes stock operation code. IE unit conversion to ordinary
            print 'Insufficient stocks: %s' % (line['stock'])
            # raise ValueError("insufficient stocks")
        self.qt_total -= line['qt']

    def __repr__(self):
        return 'name:{}, dt:{}, qt: {}, avg_price: {}, lucro:{}, prejuizo:{}'\
                    .format(self.name, self.dt.date(), self.qt_total, self.avg_price, self.profit, self.loss)


class monthsGroup():
    def __init__(self):
        self._months = {}

    def __getitem__(self, key):
        stocks = {'operations':[], 'totalization':{}}
        return self._months.setdefault(key, {'dt':datetime,
                                                'month_buy':0, 'month_sell':0,
                                                'month_gain':0, 'month_loss':0,
                                                'cumulate_gain':0, 'cumulate_loss':0,
                                                'operations':[], 'tax':{}})

    def __setitem__(self, key, value):
        self._months[key] = value

    def __iter__(self):
        return iter(self._months)

    def keys(self):
        return sorted(self._months.keys())




if __name__ == "__main__":
    b3_tax_obj = b3Tax('mirae')
    b3_tax_obj.file2object()
    b3_tax_obj.month_add_detail()
