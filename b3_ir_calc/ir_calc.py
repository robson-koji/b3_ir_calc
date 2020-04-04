# coding: utf-8

"""
This is only valid for Brazilian Real and B3 (Brazil stock exchange).
Todo localization
"""


from decimal import *
import csv, re, copy, json
from calendar import monthrange
from collections import defaultdict
from datetime import datetime, timedelta, date

# Options month codes
CALL = ['A','B','C','D','E','F','G','H','I','J','K','L']
PUT = ['M','N','O','P','Q','R','S','T','U','V','W','X']

MKT = {
        'VIS':{'threshold_exempt':20000},
        'OPV':{'threshold_exempt':0}
        }

class ObjectifyData():
    """
    Opens CSV file and objetify to a sequence of months and a list of stocks
    """
    def __init__(self, mkt_type, file, file_path="files/"):
        self.mkt_type = mkt_type
        self.file_path = file_path
        self.file = file
        self.mm = Months(mkt_type)
        self.stocks = {}
        self.running_options = RunningOptions()
        self.stocks_wallet = defaultdict()


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
            if self.mkt_type != line[3]:
                return

            # Column 10 filed, to ignore.
            if line[10]:
                return

            dt = datetime.strptime(line[0], '%d/%m/%Y').date()
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



    def file2object(self, csv_only=False):
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

                if csv_only:
                    return csv_reader

                while True:
                    try:
                        line = next(csv_reader)
                        line = self.read_line(line)
                        if not line:
                            continue

                        # if not 'KLBN11' in line['stock']:
                        #     continue

                        # Whenever the months change (for each new month),
                        # verify option expiration (OTM)
                        if not line['year_month_id'] in self.mm:
                            if self.running_options:
                                updated_options = self.running_options.chk_running_options(line)
                                self.months_update_option(updated_options)

                        # Objectify stock and months
                        stock_updated_instance = self.objectify_stock(line)
                        self.objectify_months(line, stock_updated_instance)

                        # Create or remove a running option.
                        if not self.is_stock(line['stock']): # If is option
                            if stock_updated_instance['qt_total'] == 0:
                                del self.running_options[line['stock']]
                            else:
                                self.running_options[line['stock']] = stock_updated_instance

                    except Exception as e:
                        raise

        except (IOError, OSError):
            print("Error opening / processing file")
        except StopIteration:
            pass

        # After the last operation check if there are OTM options
        updated_options = self.running_options.chk_running_options(None)
        self.months_update_option(updated_options)

        return self.mm

    def months_update_option(self, updated_options):
        if updated_options:
            for uo in updated_options:
                self.objectify_months(uo, uo)

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

        #if cp_stock['qt_total']:
        self.stocks_wallet[cp_stock['stock']] = cp_stock

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

    def get_expiring_month(self):
        """ Get the month validity on option code.
        It is the fourth letter of the option code, following
        PUT and CALL list codes """
        option_type = ''
        option_code_letter = self.running_option['stock'][4]
        try:
            expiring_month = CALL.index(option_code_letter) + 1
            option_type =  'call'
#            expiring_date = self.expiring_date(expiring_month)
        except ValueError:
            expiring_month = PUT.index(option_code_letter) + 1
            option_type =  'put'
#            expiring_date = self.calc_expiring_date(expiring_month)
        except:
            raise
        return {'option_type':option_type, 'expiring_month':expiring_month}

    def calc_expiring_date(self, expiring_month):
        """ Calculates the expiration date of the option, assuming that
        it is not possible to carry for more than a year. """
        buy_month = self.running_option['dt'].month
        current_year = datetime.today().year
        expiring_year = self.running_option['dt'].year

        """ If the month of the option is smaller than the actual month,
        it refers to the month of the next year. """
        if expiring_month < buy_month:
            expiring_year += 1
        expiring_date = date(expiring_year,
                                expiring_month,
                                monthrange(expiring_year, expiring_month)[1])
        return expiring_date

    def chk_option_expiring(self, reference_date):
        """ Discover option expiring date based on option code and buy date.
        If expired, set loss to the option object. """

        def expired_otm(expiring_date):
            """ Verify if option has lost validity """
            if reference_date > expiring_date:
                return True
            return False

        def set_option_loss():
            """ Create an operation of selling option when it expires """
            sold_option = copy.deepcopy(self.running_option)
            sold_option['loss'] = self.running_option['qt_total'] * self.running_option['avg_price']
            sold_option['value'] = 0
            sold_option['qt_total'] = 0
            sold_option['buy_sell'] = 'V'
            return sold_option

        decoded_option = self.get_expiring_month()
        expiring_date = self.calc_expiring_date(decoded_option['expiring_month'])

        if expired_otm(expiring_date):
            sold_option = set_option_loss()
            return sold_option

    def cleanup_running_option(self, clean_running_option):
        for cro in clean_running_option:
            del self._running_options[cro['name']]


    def chk_running_options(self, line):
        try:
            # Check options status against any date (reference date).
            # Using a negotiation date (year_month_id).
            reference_date = line['dt']
        except:
            # After the end of the loop of the csv file, check against today.
            reference_date = datetime.now().date()

        clean_running_option = []
        sold_options = []
        for key in self._running_options:
            self.running_option = self._running_options[key]
            sold_option = self.chk_option_expiring(reference_date)
            if sold_option:
                sold_options.append(sold_option)
                clean_running_option.append(sold_option)

        self.cleanup_running_option(clean_running_option)
        return sold_options



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


class Months():
    def __init__(self, mkt_type):
        self._months = {}
        self.mkt_type = mkt_type

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
        return True if self._months[this_month]['month_sell'] > MKT[self.mkt_type]['threshold_exempt'] else False

    def tax_calc(self, final_balance):
        return {'final_balance':final_balance, 'tax_amount': final_balance * 0.15}

    def month_add_detail(self):
        """
        Add gain, loss for all months.
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




class Report():
    def __init__(self):
        self.current_prices = dict
        self.curr_prices_dt = ''

    def get_current_quotations(self):
        """
        Whatever market data source you have.
        This is getting form a serialized JSON from Yahoo Finance, from the
        stock_price.py script
        """
        with open('files/stock_price.json', 'r') as f:
            stock_price = json.load(f)
            self.current_prices = stock_price[stock_price.keys()[0]]
            self.curr_prices_dt = stock_price.keys()[0]


    def report(self, months):
        months_keys = months.keys()
        for month in months_keys:
            month_data = months.get_month(month)
            print
            print 'Mês: {0} / Vendas no mes: {1}'.format(month, month_data['month_sell'])
            print 'Lucro: {0} / Prejuízo: {1} / Prejuizo acumulado: {2}'.format(month_data['month_gain'], month_data['month_loss'], month_data['cumulate_loss'])

            if month_data['tax']:
                print 'Balanço mês: {1} / Imposto devido: {0}'.format(month_data['tax']['tax_amount'], month_data['tax']['final_balance'])

            for ops in month_data['operations']:
                if ops['buy_sell'] == 'V':
                    if ops['profit']:
                        print "%s: %s " % (ops['stock'], ops['profit'])
                    if ops['loss']:
                        print "%s: -%s " % (ops['stock'], ops['loss'])



    def sell_losing(self, stocks_wallet, months):
        """
        On the last day of the month you can sell your stocks where you are
        losing, to reduce from your futures gains.
        """
        def current_position(stock, values):
            current_price = self.current_prices[stock]
            try:
                buy_position = values['qt_total'] * values['avg_price']
                curr_position = values['qt_total'] * round(Decimal(current_price['price']), 2)
                balance = curr_position - buy_position
                balance_pct = round((balance * 100 / buy_position), 2)
                return (stock, values, buy_position, curr_position, balance, balance_pct)
            except KeyError as e:
                # If KeyError 'avg_price', means that no buy input was provided.
                error = 'KeyError:%s' % (e)
                raise Exception(('%s: ' + error)  % (values['stock']))



        print "\n\n\nCurrent prices: %s" % (self.curr_prices_dt)
        for stock, values in stocks_wallet.items():
            if values['qt_total']:
                try:
                    (stock, values, buy_position, curr_position, balance, balance_pct) = current_position(stock, values)
                    print "%s: Qt:%d - Buy avg: R$%.2f - Cur Price: R$%s - Buy Total: R$%.2f - Cur Total: R$%.2f - Balance: R$%.2f ( %.2f%s )" % (stock, values['qt_total'], values['avg_price'], self.current_prices[stock]['price'], buy_position, curr_position, balance, balance_pct, '%')
                except Exception as e:
                    print e



"""
!!! - parametrizar o arquivo de entrada
"""


if __name__ == "__main__":
    report = Report()

    print "\n\nMercado à vista"
    print "==============="
    b3_tax_obj = ObjectifyData('VIS', 'mirae.csv', '/home/robson/invest/')
    months = b3_tax_obj.file2object()
    months.month_add_detail()

    report.report(months)
    report.get_current_quotations()
    report.sell_losing(b3_tax_obj.stocks_wallet, months)


    exit(0)

    print "\n\nOpcoes PUT"
    print "=========="
    b3_tax_obj = ObjectifyData('OPV', 'mirae.csv', '/home/robson/invest/')
    months = b3_tax_obj.file2object()
    months.month_add_detail()
    report.report(months)
