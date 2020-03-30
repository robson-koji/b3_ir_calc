# coding: utf-8

"""
This is only valid for Brazilian Real and B3 (Brazil stock exchange).
Todo localization
"""


import csv, re, copy
from decimal import *
from datetime import datetime, timedelta, date
from collections import defaultdict


class ObjectifyData():
    """
    Opens CSV file and objetify to a sequence of months and a list of stocks
    """
    def __init__(self, file, file_path="files/"):
        self.file_path = file_path
        self.file = file
        self.mm = Months()
        self.stocks = {}
        self.running_options = RunningOptions()


    def two_digits_month(self, month):
        """
        Four digits year plus two digits months for use in dict keys,
        to allows order keys
        """
        if month < 10:
            month = "0%d" % (month)
        return month

    def read_line(self, line):
        # line = [10/07/2019,1-Bovespa,C,VIS,TAEE11 UNT N2,,100,"28,69",2869,D]
        line_dict = {}
        try:
            dt = datetime.strptime(line[0], '%d/%m/%Y')
            month = self.two_digits_month(dt.month)
            year_month_id = "%d%s" % (int(dt.year), month)
            year_month_id = int(year_month_id)
            stock = line[4].split()[0]
            qt = int(line[6].replace('.', ''))

            unit_price = Decimal(line[7].replace('.', '').replace(',', '.').replace('"', ''))
            unit_price = round(unit_price, 2)

            value = Decimal(line[8].replace('.', '').replace(',', '.').replace('"', ''))
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


    def is_stock(self, asset):
        """ Whether is stock or option """
        """ There is a specific field for this on the csv """
        pattern = '^[A-Z]{4}\d+$'
        regexp = re.compile(pattern, re.IGNORECASE)
        if regexp.search(asset):
            return True
        return False



    def file2object(self):
        """
        Process file line by line using the file's returned iterator
        to permit working with large files.
        Build months object and stocks objects.
        """
        try:
            file_path = '%s%s' % (self.file_path, self.file)
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

                        # Objectify stock and months
                        stock_updated_instance = self.objectify_stock(line)
                        self.objectify_months(line, stock_updated_instance)

                        # Check month changes, to verify option expiration (OTM)
                        if not line['year_month_id'] in self.mm:
                            if self.running_options:
                                self.running_options.chk_running_options()

                        # Create or remove a running option.
                        if not self.is_stock(line['stock']): # If is option
                            if stock_updated_instance['qt_total'] == 0:
                                del self.running_options[line['stock']]
                            else:
                                self.running_options[line['stock']] = stock_updated_instance

                    except Exception as e:
                        raise

            # After the last operation check if there are OTM options
            self.running_options.chk_running_options()

        except (IOError, OSError):
            print("Error opening / processing file")
        except StopIteration:
            pass
        return self.mm


    def objectify_stock(self, line):
        """
        Receives a csv line in dict format and create a stock object.
        Each stock object instance is a stock.
        For each line, create/update the object which returns the object __dict__
        """
        # Create or get instance of a stock account
        # It is populating self.stocks, a still not used dict.
        stock = self.stocks.setdefault(line['stock'], StockCheckingAccount(line['stock']))

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


    def objectify_months(self, line, stock_updated_instance):
        #line_dict = {'year_month_id':year_month_id, 'dt':dt, 'stock':stock, 'value':value, 'buy_sell': buy_sell }
        month = line['year_month_id']
        month_dict = self.mm[month]

        # Set operation attributes
        self.mm.month_populate(month, stock_updated_instance, **line)



class RunningOptions():
    def __init__(self):
        self._running_options = {}

    def __iter__(self):
        return iter(self._running_options)

    def __getitem__(self, option):
        return self._running_options[option]

    def __setitem__(self, option, updated_instance):
        self._running_options[option] = updated_instance

    def __delitem__(self, option):
        self._running_options.pop(option, None)

    def expired_otm(self, option):
        pass
        Virou poh, entra como prejuizo.


    def chk_running_options(self):
        print self._running_options
        import pdb; pdb.set_trace()

        Fazer aqui. Verificar a data para o pohs loop do csv

        pass




class Months():
    def __init__(self):
        self._months = {}

    def __getitem__(self, month):
        stocks = {'operations':[], 'totalization':{}}
        return self._months.setdefault(month, {'dt':datetime,
                                                'month_buy':0, 'month_sell':0,
                                                'month_gain':0, 'month_loss':0,
                                                'cumulate_gain':0, 'cumulate_loss':0,
                                                'operations':[], 'tax':{}})

    def __iter__(self):
        return iter(self._months)

    def get_month(self, month):
        return self._months[month]

    def keys(self):
        return sorted(self._months.keys())

    def month_populate(self, month, stock_updated_instance, **line):
        month_dict = self._months[month]
        month_dict['dt'] = line['dt']
        if (line['buy_sell'] == 'C'):
            month_dict['month_buy'] += line['value']
        elif (line['buy_sell'] == 'V'):
            month_dict['month_sell'] += line['value']
        if stock_updated_instance is not None:
            month_dict['operations'].append(stock_updated_instance)

    def subtract_one_month(self, this_month):
        """ receives current month, returns the key of previous active month """
        self._months
        try:
            this_month_index = self.keys().index(this_month)
            if this_month_index:
                return self.keys()[this_month_index - 1]
            return None
        except:
            raise

    def cumulate_loss(self, this_month):
        previous_month = self.subtract_one_month(this_month)
        self._months[this_month]['cumulate_loss'] = self._months[this_month]['month_loss']
        if previous_month:
            self._months[this_month]['cumulate_loss'] += self._months[previous_month]['cumulate_loss']

    def threshold_exempt(self, this_month):
        """
        When the total amount sold on one month is less than R$20,000.00
        no tax are applied over gain
        """
        return True if self._months[this_month]['month_sell'] > 20000 else False

    def tax_calc(self, final_balance):
        return {'final_balance':final_balance, 'tax_amount': final_balance * 0.15}

    def month_add_detail(self):
        """
        Add gain, loss for months.
        Calculate final balance and due tax.
        """
        # import pdb; pdb.set_trace()
        for month in self.keys():
            # print "\n\n"
            # print month

            balance_current_month = 0
            # if self._months[month]['month_sell'] > 20000:
            # print "%s Total vendas : %s" % (month, self._months[month]['month_sell'])
            for operation in self._months[month]['operations']:
                if operation['buy_sell'] == 'V':
                    if operation['profit']:
                        balance_current_month += operation['profit']
                    elif operation['loss']:
                        balance_current_month -= operation['loss']

                # print operation
            if balance_current_month > 0:
                self._months[month]['month_gain'] =  balance_current_month
            elif balance_current_month < 0:
                self._months[month]['month_loss'] =  balance_current_month

            self.cumulate_loss(month)

            if self.threshold_exempt(month):
                if balance_current_month > 0:
                    final_balance = balance_current_month + self._months[month]['cumulate_loss']
                    if final_balance > 0:
                        self._months[month]['cumulate_loss'] = 0
                        self._months[month]['tax'] = self.tax_calc(final_balance)
                    elif final_balance <= 0:
                        self._months[month]['cumulate_loss'] = final_balance

            # print balance_current_month
            # print self._months[month]['month_gain']
            # print self._months[month]['month_loss']
            # print self._months[month]['cumulate_loss']
            # print self._months[month]['tax']






class StockCheckingAccount():
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





class OptionCheckingAccount(StockCheckingAccount):
    """ Not in use """
    CALL = ['A','B','C','D','E','F','G','H','I','J','K','L']
    PUT = ['M','N','O','P','Q','R','S','T','U','V','W','X']

    def put_or_call(self):
        print self.name
        import pdb; pdb.set_trace()



if __name__ == "__main__":
    b3_tax_obj = ObjectifyData('mirae.csv', '/home/robson/invest/')
    months = b3_tax_obj.file2object()
    months.month_add_detail()
    months_keys = months.keys()
    import pdb; pdb.set_trace()
    for month in months_keys:
        month_data = months.get_month(month)
        print
        print 'Mês: {0} / Vendas no mes: {1}'.format(month, month_data['month_sell'])
        print 'Lucro: {0} / Prejuízo: {1} / Prejuizo acumulado: {2}'.format(month_data['month_gain'], month_data['month_loss'], month_data['cumulate_loss'])

        if month_data['tax']:
            print 'Balanço mês: {1} / Imposto devido: {0}'.format(month_data['tax']['tax_amount'], month_data['tax']['final_balance'])
