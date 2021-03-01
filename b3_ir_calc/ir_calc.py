# coding: utf-8

"""
This is only valid for Brazilian Real and B3 (Brazil stock exchange).
Todo localization
"""

import os, csv, re, copy, json

from datetime import datetime, timedelta, date
from collections import defaultdict
from calendar import monthrange
from io import StringIO
from decimal import *

# Options month codes
CALL = ['A','B','C','D','E','F','G','H','I','J','K','L']
PUT = ['M','N','O','P','Q','R','S','T','U','V','W','X']

MKT = {
        'VIS':{'threshold_exempt':20000},
        'OPV':{'threshold_exempt':0}
        }


class InsufficientStocks(Exception):
    """ Attempt to sell more stocks than in wallet """
    pass

class StockNotFound(Exception):
    """ Attempt to sell more stocks than in wallet """
    pass


class Taxes():
    def calculate_b3_taxes(self, b3_taxes_def, type, date, value):
        """
        B3 taxes change along the time.
        self.taxes.calculate_b3_taxes(b3_taxes_def, line['dt'],  line['value'])
        """
        # b3_taxes_def - callback function
        b3_taxes_factor = b3_taxes_def(type, date)
        #self.b3_taxes = line['value'] * b3_taxes_factor
        return value * b3_taxes_factor

    def calculate_broker_taxes(self, broker_taxes_def, date):
        """
        Broker taxes change along the time.
        self.taxes.calculate_broker_taxes(b3_taxes_def, line['dt'])
        """
        broker_taxes_fees = broker_taxes_def(date)
        # self.broker_taxes = broker_taxes_fees.stock_brokering + broker_taxes_fees.stock_iss
        return broker_taxes_fees.stock_brokering + broker_taxes_fees.stock_iss

    def calculate_irpf_withholding(self, type, value):
        """
        IRPF taxes change along the time.
        self.taxes.calculate_irpf_withholding('regular', line['value'])
        """
        #self.irpf_withholding = line['value'] * Decimal(0.00005)
        irpf_withholding = {'regular': value * Decimal(0.00005),
                                'daytrade': value * Decimal(0.01),}
        return irpf_withholding[type]


class ObjectifyData():
    """
    Opens CSV file and objetify to a sequence of months and a list of stocks
    """
    def __init__(self, mkt_type, file, ignore_taxes, path="files/", broker_taxes=None, b3_taxes=None, corporate_events=None, get_dayt=False):
        self.mkt_type = mkt_type
        self.file_path = path
        self.file = file
        self.mm = Months(mkt_type, broker_taxes, b3_taxes)
        self.stocks = {}
        self.running_options = RunningOptions()
        self.stocks_wallet = defaultdict()
        self.illegal_operation = defaultdict(list)
        self.ce = corporate_events()
        self.b3_taxes_def = b3_taxes
        self.broker_taxes_def = broker_taxes
        self.previous_day = None
        self.days =  defaultdict(lambda: defaultdict(list))
        self.get_dayt = get_dayt
        #self.has_dayt =  defaultdict(lambda: defaultdict(lambda: defaultdict()))
        self.has_dayt =  defaultdict(lambda: defaultdict(lambda: {'has_sold':False, 'has_bought':False}))
        self.dayt = DayTrade(self.mkt_type)
        self.taxes = Taxes()
        self.ignore_taxes = ignore_taxes

        file_path = '%s%s' % (self.file_path, self.file)
        if not os.path.exists(file_path):
            raise FileNotFoundError('FileNotFound: %s' % (file_path))

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
            # import pdb; pdb.set_trace()
            if len(line) == 11 and line[10]:
                return

            """
            !!! Compatibilizar as datas. Provavelmente tudo com 2 digitos no ano.
            """
            dt = datetime.strptime(line[0], '%d/%m/%Y').date()
            month = self.two_digits_month(dt.month)
            year_month_id = "%d%s" % (int(dt.year), month)
            year_month_id = int(year_month_id)
            stock = line[4].split()[0]
            qt = int(line[6].replace('.', ''))

            # Comma separator for decimal
            if ',' in line[7]:
                unit_price = Decimal(line[7].replace('.', '').replace(',', '.').replace('"', ''))
            # Dot separator for decimal
            else:
                unit_price = Decimal(line[7].replace('"', ''))
            unit_price = round(unit_price, 2)
#            print(line)
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
            # print(line_dict)
            # import pdb; pdb.set_trace()
            return line_dict
        except Exception as e:
            print(e)
            raise


    def is_stock(self, asset):
        """ Whether is stock or option """
        """ There is a specific field for this on the csv """
        pattern = '^[A-Z]{5}\d+$'
        regexp = re.compile(pattern, re.IGNORECASE)
        # import pdb; pdb.set_trace()
        if regexp.search(asset):
            return False
        return True



    def file2object(self, csv_only=False, stock_detail=None):
        """
        Process file line by line using the file's returned iterator
        to permit working with large files.
        Build months object and stocks objects.
        """
        try:
            file_path = '%s%s' % (self.file_path, self.file)

            with open(file_path) as file_handler:
                # import pdb; pdb.set_trace()
                csv_reader = csv.reader(file_handler, quotechar='"', delimiter=',')

                # To remove excel header if exists
                # next(csv_reader, None)
                csv_reader = reversed(list(csv_reader))

                if csv_only:
                    return csv_reader

                while True:
                    try:
                        line = next(csv_reader)
                        line = self.read_line(line)
                        if not line:
                            continue

                        # For History stock detail
                        if stock_detail is not None:
                            stock_detail_lst = [stock_detail]
                            check_dayt =  any(item in stock_detail_lst for item in self.dayt._has_dayts[self.previous_day].keys())
                            if stock_detail in self.ce.dict_deconversion_events.keys():
                                stock_detail_lst.append(self.ce.dict_deconversion_events[stock_detail])
                            if not line['stock'] in stock_detail_lst and not check_dayt:
                                continue

                        # if not 'HAPV3' in line['stock'] and not 'HAPV3' in self.dayt._has_dayts[self.previous_day].keys():
                        #       continue

                        # if line['year_month_id'] != 202004:
                        #     continue

                        # Whenever the months change (for each new month),
                        # verify option expiration (OTM)
                        if not line['year_month_id'] in self.mm:
                            if self.running_options:
                                updated_options = self.running_options.chk_running_options(line)
                                self.months_update_option(updated_options)

                        # Objectify stock and months
                        # stock_updated_instance = self.objectify_stock(line)
                        # if not stock_updated_instance:
                        #     continue
                        self.verify_intraday(line)
                        # self.objectify_months(stock_updated_instance)

                        """
                        Todo
                        # Create or remove a running option.
                        if not self.is_stock(line['stock']): # If is option
                            if stock_updated_instance.qt_total == 0:
                                del self.running_options[line['stock']]
                            else:
                                self.running_options[line['stock']] = stock_updated_instance
                        """


                        # if stock_detail is not None:
                        #     line_dt = datetime.today().date()
                        #     event = False
                        #     while event == False:
                        #         event = self.apply_event(line_dt)
                        #         try:
                        #             self.objectify_months(self.stocks_wallet[line['stock']])
                        #         except:
                        #             import pdb; pdb.set_trace()
                        #             pass

                    except Exception as e:
                        raise



        except (IOError, OSError):
            print("Error opening / processing file")
        except StopIteration:
            pass

        line_dt = datetime.today().date()
        event = False
        while event == False:
            event = self.apply_event(line_dt)

        # After the last operation check if there are OTM options
        updated_options = self.running_options.chk_running_options(None)
        self.months_update_option(updated_options)


        # After the last operation, insert last not insert day on month
        self.previous_day = line['dt']
        #self.objectify_months(stock_updated_instance.dt)
        # import pdb; pdb.set_trace()
        self.reconcile_day()


        # DayTrade - self.mm has all months and daytrades
        # keys = list(self.mm[202003]['dayt']._has_dayts.keys())
        # print(self.mm[202003]['dayt'][keys[0]])

        return self.mm
        # self.mm[202011]['dayt']._dayts['2020-11-3']

    def months_update_option(self, updated_options):
        if updated_options:
            for uo in updated_options:
                self.objectify_months(uo)

    def apply_event(self, line_dt):
        """ Apply corporate events on companies """
        # print(self.stocks_wallet)
        # import pdb; pdb.set_trace()
        #(events, date_event, last) =  self.ce.check_event(line_dt)

        list_of_events =  self.ce.check_event(line_dt)

        # import pdb; pdb.set_trace()
        for loe in list_of_events:
            events = loe[0]
            date_event = loe[1]
            last = loe[2]
            if events:
                """
                {'stock': 'BMGB11', 'event': 'desdobramento','data_ex': '11292019', 'group_valid': '1',
                'operator': '*', 'qtt_operation': '4','stock_code_change': 'BMGB4'}
                """
                for event in events:
                    try:
    #                    [value for key, value in programs.items() if 'new york' in key.lower()]
                        stock = [value for key, value in self.stocks.items() if event['stock'].lower() in key.lower()]
                        if not stock:
                            continue
                        update_stock = stock[0]
                        update_stock.update_event(event)
                        # import pdb; pdb.set_trace()
                        if event['asset_code_new']:
                            # Change old stock to new stock in stock dict.
                            self.stocks[event['asset_code_new']] = self.stocks.pop(event['asset_code_old'])
                            self.stocks_wallet[event['asset_code_new']] = self.stocks_wallet.pop(event['asset_code_old'])

                        # deep copy operation values to stock_wallet.
                        # This is for corporative events.
                        # objectify_stock() calls it too. It is ok to call twice.
                        # !!! changed from .__dict__ to object. Hope this is ok.
                        #cp_stock = copy.deepcopy(update_stock.__dict__)
                        cp_stock = copy.deepcopy(update_stock)
                        self.stocks_wallet[stock[0].name] = cp_stock


                    except:
                        print("Error event apply: %s" % (event['stock']))

                # Delete applyed event
                self.ce.delete_event(date_event)

            # print(self.stocks_wallet)
            # import pdb; pdb.set_trace()

            if last == 1:
                return True

    def objectify_stock(self, line):
        """
        Receives a csv line in dict format and create a stock object.
        Each stock object instance is a stock.
        For each line, create/update the object which returns the object __dict__
        """


        self.apply_event(line['dt'])


        stock = self.stocks.setdefault(line['stock'], StockCheckingAccount(line['stock']))



        # Set operation attributes
        stock.start_operation(**line)
        stock.calculate_position(**line)

        # Calculate and set instance values
        if line['buy_sell'] == 'C':
            stock.buy(**line)
        if line['buy_sell'] == 'V':
            # import pdb; pdb.set_trace()
            try:
                stock.sell(**line)
            except InsufficientStocks:
                print('InsufficientStocks:%s' % stock)
                line['exception'] = InsufficientStocks('%s: Insufficient stocks to sale (%s)'  % (line['stock'], line['dt']))
                self.illegal_operation[line['stock']].append(line)
                return None

        if not self.ignore_taxes:
            stock.b3_taxes = self.taxes.calculate_b3_taxes(self.b3_taxes_def, 'regular', line['dt'],  line['value'])
            stock.broker_taxes = self.taxes.calculate_broker_taxes(self.broker_taxes_def, line['dt'])
            stock.irpf_withholding = self.taxes.calculate_irpf_withholding('regular', line['value'])

        cp_stock = copy.deepcopy(stock)
        self.stocks_wallet[cp_stock.stock] = cp_stock

        return cp_stock


    def reconcile_day(self):
        """ Check if previous day has day trade """
        stocks = list(self.dayt._has_dayts[self.previous_day].keys())
        month = None
        for stock in self.dayt._has_dayts[self.previous_day].keys():
            # import pdb; pdb.set_trace()
            month = self.dayt[self.previous_day][stock]['operations']['sold'][0]['year_month_id']
            """ If stock has daytrade """
            if 'operations' in self.dayt[self.previous_day][stock]:
                """ remove from month regular trades """
                self.days[self.previous_day].pop(stock)

        """ Daytrade reconciliation """
        if self.get_dayt:
            self.dayt.dayt_consolidate_day()

        """
        Insert virtual orders remaining from daytrade.
        Why virtual orders? Because sometimes bought and sold orders on daytrade,
        doesnt match exact, and the rest return to the position wallet.
        Once this virtual orders returns to wallet, it can matches against old,
        or future orders.
        """
        for stock in self.dayt._has_dayts[self.previous_day].keys():
            self.days[self.previous_day][stock] = self.dayt[self.previous_day][stock]['operations']['bought'] + \
                                                        self.dayt[self.previous_day][stock]['operations']['sold']
            # print ("Bought: %s" % (str(self.dayt[self.previous_day][stock]['operations']['bought'])))
            # print ("Sold: %s" % (str(self.dayt[self.previous_day][stock]['operations']['sold'])))
        # print ('Previous_day: %s' % (str(self.days[self.previous_day])))
        # import pdb; pdb.set_trace()



        """ Objectify stocks and add operations to month """
        # import pdb; pdb.set_trace()

        for stock in self.days[self.previous_day]:
            for line in self.days[self.previous_day][stock]:
                stock_updated_instance = self.objectify_stock(line)
                if not stock_updated_instance:
                    continue

                """ Call month object and add regular trades """
                self.objectify_months( stock_updated_instance )

        if month: self.month_add_dayt(month, self.previous_day, self.dayt._has_dayts)

        # Cleanup daytrade objects
        try:
            del self.dayt[self.previous_day]
            del self.dayt._has_dayts[self.previous_day]
        except:
            # History detail bugs here.
            pass

        # Cleanup regular trades object
        del self.days[self.previous_day]

        remaining_days = list(self.days)
        if remaining_days:
            for rd in remaining_days:
                self.previous_day = rd
                self.reconcile_day()




    def verify_intraday(self, line):
        """
        Group stocks by day, check daytrade, objectify stocks and send to month.
        We dont care about intraday operation, so they are discharged but while daytrade
        """
        date = line['dt']
        stock = line['stock']
        buy_sell = line['buy_sell']

        """ Start daytrade objects """
        self.dayt[date]
        self.dayt.dayt_populate(line)

        """ Populate day data structure """
        self.days[date][stock].append(line)

        # print(date)
        # print(self.previous_day)

        """ Day has changed. Reconcile day. """
        if self.previous_day is not None and date != self.previous_day:
            # print( '++++')
            # print(date)
            # print(stock)
            # print()
            self.days[self.previous_day][stock].reverse()
            self.reconcile_day()

        self.previous_day = date


    def objectify_months(self, stock_updated_instance):
        month = stock_updated_instance.year_month_id
        # Initialize month object
        month_dict = self.mm[month]
        # Set operation attributes
        self.mm.month_populate(month, stock_updated_instance)


    def month_add_dayt(self, month, day_of_dayt, stock_dayt):
        self.mm[month]['dayt'][day_of_dayt] = stock_dayt[day_of_dayt]


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


# class CorporateEvent():
#     # scsv = """stock, event, data_ex, data_new, 'group_valid', operator, qtt_operation, stock_code_change,
#     #         BMGB11, desdobramento, 11292019, 11292019, 1, *, 4, BMGB4
#     #         BBDC3, bonificacao, 04142020, 04162020, 10, *, 1.1,
#     #         BBDC4, bonificacao, 04142020, 04162020, 10, *, 1.1,
#     #         JSLG3, conversao,09182020, 09182020, 1, , , SIMH3
#     #         MGLU3, desdobramento,10142020, 10162020, 1, *, 4,
#     #         HAPV3, desdobramento,11252020, 11272020, 1, *, 5,"""
#
#     def __init__(self):
#
#         events = CorporateEvent.objects.all()
#
#         """
#         f = StringIO(self.scsv)
#         reader = csv.reader(f, skipinitialspace=True, delimiter=',')
#         self.dict_ce = defaultdict(list)
#         next(reader, None)  # skip the headers
#
#         for row in reader:
#             date_ex = datetime.strptime(row[2], '%m%d%Y').date()
#             date_new = datetime.strptime(row[3], '%m%d%Y').date()
#             self.dict_ce[date_ex].append( {'stock': row[0],'event': row[1],
#                                 'date_ex': row[2],'group_valid': row[4],
#                                 'operator': row[5],
#                                 'qtt_operation': row[6],
#                                 'stock_code_change': row[7],})
#         """
#
#     def check_event(self, line_dt):
#         for date_event in self.dict_ce:
#             # Apply event only after the event date.
#             # Checks against all trading data, or today.
#             if date_event <= line_dt:
#                 return (self.dict_ce[date_event], date_event, len(self.dict_ce.keys()))
#         return (None, None, None)
#
#     def delete_event(self, event_date):
#         try:
#             del self.dict_ce[event_date]
#         except:
#             import pdb; pdb.set_trace()
#


class StockCheckingAccount():
    import random, operator

    operators = {'+': operator.add,
                '-': operator.sub,
                '*': operator.mul}

    def __init__(self, name):
        self.name = name
        self.qt_total = 0
        self.avg_price = 0
        self.qt_total_prev = 0 # for balance
        self.avg_price_prev = 0 # for balance
        self.my_position = Decimal()
        self.mkt_position = Decimal()
        self.unit_price = Decimal()
        self.b3_taxes =  Decimal()
        self.broker_taxes =  Decimal()
        self.irpf_withholding = 0
        self.profit = 0
        self.loss = 0
        self.dt = date


    @property
    def avg_price(self):
        return self._avg_price

    @avg_price.setter
    def avg_price(self, new_avg_price):
        self._avg_price = new_avg_price

    @property
    def avg_price_prev(self):
        return self._avg_price_prev

    @avg_price_prev.setter
    def avg_price_prev(self, avg_price):
        self._avg_price_prev = avg_price

    @property
    def qt_total_prev(self):
        return self._qt_total_prev

    @qt_total_prev.setter
    def qt_total_prev(self, qt_total):
        self._qt_total_prev = qt_total


    def new_avg_price(self, qt, unit_price):
        # import pdb; pdb.set_trace()
        current_position = abs(self.qt_total) * self.avg_price
        new_dock = qt * unit_price
        new_avg_price = (current_position + new_dock) / (abs(self.qt_total) + qt)
        self.avg_price_prev = self.avg_price
        self.avg_price = new_avg_price

    def start_operation(self, **kwargs):
        # Pass all csv line values to stockCheckingAccount instance
        self.__dict__.update(kwargs)
        # Init profit and loss for this operation
        # Will calculate this based on the avg_price * sell price.
        self.profit = 0
        self.loss = 0

    def calculate_position(self, **line):
        if self.qt_total > 0:
            self.my_position = round(Decimal(self.qt_total * self.avg_price), 2)
        else:
            self.my_position = 0
        self.mkt_position = round(Decimal(self.qt_total * line['unit_price']), 2)
        self.unit_price = line['unit_price']


    def profit_loss(self, oper, qt, unit_price):
        if abs(qt) > abs(self.qt_total):
            qt = abs(self.qt_total)

        if oper == 'short':
            if unit_price <= self.avg_price:
                self.profit += (qt * unit_price) - (qt * self.avg_price)
            elif unit_price >= self.avg_price:
                self.loss += (qt * self.avg_price) - (qt * unit_price)
        else:
            if unit_price <= self.avg_price:
                self.loss += (qt * self.avg_price) - (qt * unit_price)
            elif unit_price >= self.avg_price:
                self.profit += (qt * unit_price) - (qt * self.avg_price)

        self.loss = abs(self.loss)
        self.profit = abs(self.profit)

    def buy(self, **line):
        # Regular operation
        if self.qt_total >= 0:
            self.new_avg_price(line['qt'], line['unit_price'])
        # Short selling
        else:
            self.profit_loss('short', line['qt'], line['unit_price'])

        self.qt_total_prev = self.qt_total
        self.qt_total += line['qt']


    def sell(self, **line):
        # Regular operation
        if self.qt_total >= line['qt']:
            self.profit_loss('regular', line['qt'], line['unit_price'])
            # if line['qt'] > self.qt_total:
            #     # import pdb; pdb.set_trace()
            #     raise InsufficientStocks()

        # Short selling
        else:
            self.new_avg_price(line['qt'], line['unit_price'])

        self.qt_total -= line['qt']
        if self.qt_total == 0:
            self.qt_total_prev = 0
            self.avg_price_prev = 0
            self.avg_price = 0


    def update_event(self, stock_event):
        """
        Update corporate event at the current position of the stock checking account.
        {'stock': 'BMGB11', 'event': 'desdobramento', 'data_ex': '11292019', 'group_valid': '1',
        'operator': '*', 'qtt_operation': '4', 'stock_code_change': 'BMGB4'}
        """
        if stock_event['event'] == 'desdobramento':
            self.qt_total = self.operators[stock_event['operator']](
                                self.qt_total, int(stock_event['qtt_operation']))
            self.avg_price = Decimal(self.avg_price/int(stock_event['qtt_operation']))

            # HAPV3 - nao funcionou
           # O problema estah aqui no . gravado o hapv3 antes de alterar

            # self.qt = self.operators[stock_event['operator']](
            #                     self.qt, int(stock_event['qtt_operation']))
            # self.unit_price = Decimal(self.unit_price/int(stock_event['qtt_operation']))

        elif stock_event['event'] == 'bonificacao':
            self.qt_total = int(self.operators[stock_event['operator']](
                                self.qt_total, Decimal(stock_event['qtt_operation'])))

            self.avg_price = self.value / self.qt_total
            # import pdb; pdb.set_trace()

        if stock_event['asset_code_new']:
             self.stock = self.name = stock_event['asset_code_new']

        # import pdb; pdb.set_trace()
        return None

    def __repr__(self):
        return 'name:{}, dt:{}, qt_total: {}, avg_price: {}, lucro:{}, prejuizo:{}'\
            .format(self.name, self.dt, self.qt_total, self.avg_price, self.profit, self.loss)



class DayTrade():
    def __init__(self, mkt_type):
        self._dayts = {}
        self.mkt_type = mkt_type
        #self._has_dayts = defaultdict(lambda: {'operations':[]})
        self._has_dayts = defaultdict(dict)

    def __getitem__(self, date):
        return self._dayts.setdefault(date, defaultdict(lambda: {
                                        'operations':{'bought':[], 'sold':[]},
                                        'original_operations':{'bought':[], 'sold':[]},
                                        'has_bought': False, 'has_sold': False,
                                        'qt_total_dayt': 0,
                                        'total_amount_sold_dayt': Decimal(), 'total_amount_bought_dayt': Decimal(),
                                        'operation_result':Decimal(),
                                        'qt_initial_operations':0, 'qt_remaining_operations': 0,
                                        'qt_real_dt_operations':0,
                                        'reconciled_bought_operations': [],'reconciled_sold_operations': [],
                                        'avg_price_bought':Decimal(), 'avg_price_sold':Decimal() }))


    def __delitem__(self, key):
        del self._dayts[key]

    def __iter__(self):
        return iter(self._dayts)

    def get_day(self, dt):
        return self._dayts[dt]

    def keys(self):
        return sorted(self._dayts.keys())

    def dayt_populate(self, line):
        date = line['dt']
        stock = line['stock']
        buy_sell = line['buy_sell']
        dayt_dict = self._dayts[date]

        if buy_sell == 'C':
            dayt_dict[stock]['has_bought'] = True
            dayt_dict[stock]['operations']['bought'].append(line)
        elif buy_sell == 'V':
            dayt_dict[stock]['has_sold'] = True
            dayt_dict[stock]['operations']['sold'].append(line)

        if dayt_dict[stock]['has_bought'] and dayt_dict[stock]['has_sold']:
            # print("%s: %s" % (str(date), str(stock)))
            self._has_dayts[date][stock] = dayt_dict[stock]


    def match_daytrade_operations(self,stock_dayt, bought, sold):
        """
        Match daytrade operations and calculate results
        Reconcile to match orders quantity, until ends bought or sold orders.
        If rests orders, they goes to the position wallet.

        stock_dayt['qt_real_dt_operations'] may be different of
            len(stock_dayt['reconciled_bought_operations']) +
                len(stock_dayt['reconciled_sol_operations'])
        because reconciliation process may split operations to match buy and sell,
        and may rest one part of the operation that returns to the wallet.

        stock_dayt['operations'] become remaining operations to loop out thought
        rest of operations, untill there are no more orders to match, returning the
        remaining order(s).
        """

        if bought['qt'] > sold['qt']:
            """ Buy up to sold position """
            remaining_order  = copy.deepcopy(bought)
            remaining_order ['qt'] = bought['qt'] - sold['qt']
            remaining_order ['value'] = remaining_order ['unit_price'] * remaining_order ['qt']
            # Append remaining order to the refered list.
            self.bought_operations.append(remaining_order )


            reconciled_order = copy.deepcopy(bought)
            reconciled_order['qt'] = sold['qt']
            reconciled_order['value'] = reconciled_order['unit_price'] * reconciled_order['qt']
            stock_dayt['reconciled_bought_operations'].append(reconciled_order)
            stock_dayt['reconciled_sold_operations'].append(sold)

            sold['result'] = (sold['unit_price'] * sold['qt']) - (bought['unit_price'] * sold['qt'])
            stock_dayt['operation_result'] += sold['result']
            stock_dayt['qt_total_dayt'] += sold['qt'] * 2
            stock_dayt['total_amount_bought_dayt'] += (bought['unit_price'] * sold['qt'])
            stock_dayt['total_amount_sold_dayt'] += (sold['unit_price'] * sold  ['qt'])


        elif sold['qt'] > bought['qt']:
            """ Sell up to bought position """
            remaining_order  = copy.deepcopy(sold)
            remaining_order ['qt'] = sold['qt'] - bought['qt']
            remaining_order ['value'] = remaining_order ['unit_price'] * remaining_order ['qt']
            # Append remaining order to the refered list.
            self.sold_operations.append(remaining_order )

            reconciled_order = copy.deepcopy(sold)
            reconciled_order['qt'] = bought['qt']
            reconciled_order['value'] = reconciled_order['unit_price'] * reconciled_order['qt']
            stock_dayt['reconciled_sold_operations'].append(reconciled_order)
            stock_dayt['reconciled_bought_operations'].append(bought)

            reconciled_order['result'] = (sold['unit_price'] * bought['qt']) - (bought['unit_price'] * bought['qt'])
            stock_dayt['operation_result'] += reconciled_order['result']
            stock_dayt['qt_total_dayt'] += bought['qt'] * 2
            stock_dayt['total_amount_bought_dayt'] += (bought['unit_price'] * bought['qt'])
            stock_dayt['total_amount_sold_dayt'] += (sold['unit_price'] * bought['qt'])
        else:
            stock_dayt['reconciled_bought_operations'].append(bought)
            stock_dayt['reconciled_sold_operations'].append(sold)

            sold['result'] = (sold['unit_price'] * sold['qt']) - (bought['unit_price'] * sold['qt'])
            stock_dayt['operation_result'] += sold['result']
            stock_dayt['qt_total_dayt'] += sold['qt'] * 2
            stock_dayt['total_amount_bought_dayt'] +=  (bought['unit_price'] * bought['qt'])
            stock_dayt['total_amount_sold_dayt'] += (sold['unit_price'] * sold['qt'])


    def dayt_consolidate_by_stock(self, stock_dayt):
        """ Check daytrade by day, by stock """
        self.bought_operations = stock_dayt['operations']['bought']
        self.sold_operations = stock_dayt['operations']['sold']
        self.bought_operations.reverse()
        self.sold_operations.reverse()

        # Store the real qt daytrading operations
        stock_dayt['qt_initial_operations'] = len(self.bought_operations) + len(self.sold_operations)

        while self.bought_operations:
            if self.sold_operations:
                bought = self.bought_operations.pop()
                sold = self.sold_operations.pop()
                self.match_daytrade_operations(stock_dayt, bought, sold)
            else:
                break

        # After loop all operations, lenght may change.
        # These stocks go back to position wallet.
        stock_dayt['qt_remaining_operations'] = len(self.bought_operations) + len(self.sold_operations)

        # These is just for statistics.
        stock_dayt['qt_real_dt_operations'] = stock_dayt['qt_initial_operations'] -\
                                                stock_dayt['qt_remaining_operations']


        stock_dayt['reconciled_operations'] = zip(stock_dayt['reconciled_bought_operations'],\
                                                        stock_dayt['reconciled_sold_operations'])
        # print("stock_dayt['operations']")
        # print(stock_dayt['operations'])
        #
        # print('operation result')
        # print(stock_dayt['operation_result'] )

        return stock_dayt


    def dayt_consolidate_day(self):
        for day in self._has_dayts.keys():
            for stock in self._has_dayts[day]:
                stock_dayt = self._has_dayts[day][stock]
                stock_dayt['original_operations'] = copy.deepcopy(stock_dayt['operations'])
                print('---')
                print(day)
                print(stock)
                self.dayt_consolidate_by_stock(stock_dayt)



class Months():
    def __init__(self, mkt_type, broker_taxes=None, b3_taxes=None):
        self._months = {}
        self.mkt_type = mkt_type
        self.taxes = Taxes()
        self.broker_taxes_def = broker_taxes
        self.b3_taxes_def = b3_taxes
        self.ignore_taxes = False

    def __getitem__(self, month):
        # stocks = {'operations':[], 'totalization':{}}
        return self._months.setdefault(month, {'dt':datetime,
                'month_buy':0, 'month_sell':0, 'qt_buy':0, 'qt_sell':0,
                'month_gain':0, 'month_loss':0, 'month_net_gain':0, 'month_net_loss':0,
                'cumulate_gain':0, 'cumulate_loss':0, 'prev_month_cumulate_loss':0,
                'b3_taxes':0, 'broker_taxes':0, 'irpf_withholding':0, 'sum_taxes':0,
                'tax':{}, 'operations':defaultdict(list), 'dayt': defaultdict(dict),
                'dayt_summary': defaultdict(Decimal)})

    def __iter__(self):
        return iter(self._months)

    def get_month(self, month):
        return self._months[month]

    def keys(self):
        return sorted(self._months.keys())

    def month_populate(self, month, stock_updated_instance):
        line = stock_updated_instance
        # if 'BMGB' in line['stock']:
        #     import pdb; pdb.set_trace()
        # import pdb; pdb.set_trace()

        month_dict = self._months[month]
        month_dict['dt'] = line.dt

        if (line.buy_sell == 'C'):
            month_dict['month_buy'] += line.value
        elif (line.buy_sell == 'V'):
            month_dict['month_sell'] += line.value
        if stock_updated_instance is not None:
            month_dict['operations'][line.stock].append(stock_updated_instance)

    def subtract_one_month(self, this_month):
        """ receives current month, returns the key of previous active month """
        try:
            this_month_index = self.keys().index(this_month)
            if this_month_index:
                return self.keys()[this_month_index - 1]
            return None
        except:
            raise

    def cumulate_loss(self, this_month, previous_month):
        this_month['cumulate_loss'] = this_month['month_net_loss']
        if previous_month:
            this_month['cumulate_loss'] += previous_month['cumulate_loss']
            this_month['prev_month_cumulate_loss'] = previous_month['cumulate_loss']


    def cumulate_gain(self, this_month, previous_month):
        this_month['cumulate_gain'] = this_month['month_net_gain']
        if previous_month:
            this_month['cumulate_gain'] += previous_month['cumulate_loss']
        if this_month['cumulate_gain'] < 0 : this_month['cumulate_gain'] = 0


    def threshold_exempt(self, this_month):
        """
        When the total amount sold on one month is less than R$20,000.00
        no tax are applied over gain
        """
        return True if self._months[this_month]['month_sell'] > MKT[self.mkt_type]['threshold_exempt'] else False


    def tax_calc(self, final_balance):
        #return {'final_balance':final_balance, 'tax_amount': final_balance * 0.15}
        #import pdb; pdb.set_trace()
        return {'final_balance':final_balance, 'tax_amount': final_balance * Decimal(0.15)}


    def finance_result(self, this_month, previous_month, balance_current_month, sum_taxes=0 ):
        balance_net_current_month = balance_current_month - sum_taxes

        if balance_current_month < 0:
            this_month['month_loss'] =  balance_current_month
        elif balance_current_month > 0:
            this_month['month_gain'] =  balance_current_month

        if balance_net_current_month < 0:
            this_month['month_net_loss'] = balance_net_current_month
        elif balance_net_current_month > 0:
            this_month['month_net_gain'] = balance_net_current_month

        self.cumulate_loss(this_month, previous_month)
        self.cumulate_gain(this_month, previous_month)

        # if self.threshold_exempt(month):
        if balance_net_current_month > 0:
            final_balance = balance_net_current_month + this_month['cumulate_loss']
            if final_balance > 0:
                this_month['cumulate_loss'] = 0
                this_month['cumulate_gain'] = final_balance
                this_month['tax'] = self.tax_calc(Decimal(final_balance))
            elif final_balance <= 0:
                this_month['cumulate_gain'] = 0
                this_month['cumulate_loss'] = final_balance

        # print(balance_current_month)
        # print(this_month['month_gain'])
        # print(this_month['month_loss'])
        # print(this_month['cumulate_loss'])
        # print(this_month['tax'])


    def summarize_regular_operations(self):
        balance_current_month = 0
        for stock, values in self.this_month_obj ['operations'].items():
            for operation in values:
                if operation.buy_sell == 'V':
                    self.this_month_obj ['qt_sell'] += 1
                    # if operation.profit:
                    #     balance_current_month += operation.profit
                    # elif operation.loss:
                    #     balance_current_month -= operation.loss
                else:
                    self.this_month_obj ['qt_buy'] += 1

                if operation.profit:
                    balance_current_month += operation.profit
                elif operation.loss:
                    balance_current_month -= operation.loss

                self.this_month_obj ['b3_taxes'] += operation.b3_taxes
                self.this_month_obj ['broker_taxes'] += operation.broker_taxes
                self.this_month_obj ['irpf_withholding'] += operation.irpf_withholding
        self.this_month_obj ['b3_taxes'] = round(Decimal(self.this_month_obj ['b3_taxes']), 2)
        self.this_month_obj ['broker_taxes'] = round(Decimal(self.this_month_obj ['broker_taxes']), 2)
        self.this_month_obj ['irpf_withholding'] = round(Decimal(self.this_month_obj ['irpf_withholding']), 2)
        self.this_month_obj ['sum_taxes'] = self.this_month_obj ['b3_taxes'] +\
                                                self.this_month_obj ['broker_taxes'] +\
                                                        self.this_month_obj ['irpf_withholding']

        self.finance_result(self.this_month_obj, self.previous_month_obj, balance_current_month, self.this_month_obj ['sum_taxes'] )



    def summarize_daytrading_operations(self):
        # print('\n\n')
        # print('summarze_daytrading_operations')
        for day, values in self.this_month_obj ['dayt'].items():
            print(day)
            for stock in values:
                print(stock)
                # print(values[stock])
                self.this_month_obj ['dayt_summary']['total_amount_bought_dayt'] += values[stock]['total_amount_bought_dayt']
                self.this_month_obj ['dayt_summary']['total_amount_sold_dayt'] += values[stock]['total_amount_sold_dayt']

                # import pdb; pdb.set_trace()
                # # For each stock, calc taxes
                dayt_sum_value_operations =  values[stock]['total_amount_bought_dayt'] + \
                                                    values[stock]['total_amount_sold_dayt']

                if not self.ignore_taxes:
                    self.this_month_obj ['dayt_summary']['b3_taxes'] += self.taxes.calculate_b3_taxes(self.b3_taxes_def, 'daytrade', day, dayt_sum_value_operations)
                    self.this_month_obj ['dayt_summary']['broker_taxes'] += self.taxes.calculate_broker_taxes(self.broker_taxes_def, day)
                    if values[stock]['operation_result'] > 0:
                        self.this_month_obj ['dayt_summary']['irpf_withholding'] += self.taxes.calculate_irpf_withholding('daytrade', values[stock]['operation_result'])
                        # print(values[stock])
                        # print(self.this_month_obj ['dayt_summary'])


        if not self.ignore_taxes:
            self.this_month_obj ['dayt_summary']['b3_taxes'] = round(Decimal(self.this_month_obj ['dayt_summary']['b3_taxes']), 2)
            self.this_month_obj ['dayt_summary']['broker_taxes'] = round(Decimal(self.this_month_obj ['dayt_summary']['broker_taxes']), 2)
            self.this_month_obj ['dayt_summary']['irpf_withholding'] = round(Decimal(self.this_month_obj ['dayt_summary']['irpf_withholding']), 2)

        if not self.ignore_taxes:
            self.this_month_obj ['dayt_summary']['sum_taxes'] = self.this_month_obj ['dayt_summary']['b3_taxes'] +\
                                                self.this_month_obj ['dayt_summary']['broker_taxes'] +\
                                                        self.this_month_obj ['dayt_summary']['irpf_withholding']

        balance_current_month = self.this_month_obj ['dayt_summary']['total_amount_sold_dayt'] -\
                                    self.this_month_obj ['dayt_summary']['total_amount_bought_dayt']

        if self.previous_month_obj:
            self.finance_result(self.this_month_obj ['dayt_summary'], self.previous_month_obj ['dayt_summary'], balance_current_month, self.this_month_obj ['dayt_summary']['sum_taxes']  )
        else:
            self.finance_result(self.this_month_obj ['dayt_summary'], None, balance_current_month, self.this_month_obj ['dayt_summary']['sum_taxes']  )


        # import pdb; pdb.set_trace()
        # print('\n\ndayt_summary')
        # print(self.this_month_obj ['dayt_summary'])


    def month_add_detail(self, get_dayt=False, ignore_taxes=False):
        """
        Add gain, loss for all months.
        Calculate final balance and due tax.
        """
        self.ignore_taxes = ignore_taxes

        # import pdb; pdb.set_trace()
        for month in self.keys():
            previous_month = self.subtract_one_month(month)
            # print("\n\n"
            # print(month)
            # import pdb; pdb.set_trace()

            # if self.this_month_obj ['month_sell'] > 20000:
            # print("%s Total vendas : %s" % (month, self.this_month_obj ['month_sell'])

            self.this_month_obj = self._months[month]
            if not previous_month in self._months:
                self.previous_month_obj = None
            else:
                self.previous_month_obj = self._months[previous_month]

            # Always have to summarize,
            # to get former month cumulate loss if exists.
            self.summarize_regular_operations()
            if get_dayt:
                self.summarize_daytrading_operations()






class Report():
    def __init__(self, stock_price_file, stocks_wallet, months):
        self.current_prices = dict
        self.curr_prices_dt = ''
        self.illegal_operation = defaultdict(list)
        self.months = months
        self.stock_price_file = stock_price_file
        self.stocks_wallet = stocks_wallet

    def get_current_quotations(self):
        """
        Whatever market data source you have.
        This is getting form a serialized JSON from Yahoo Finance, from the
        stock_price.py script
        """
        # import pdb; pdb.set_trace()
        with open(self.stock_price_file, 'r') as f:
            stock_price = json.load(f)
            self.current_prices = stock_price[list(stock_price.keys())[0]]
            self.curr_prices_dt = list(stock_price.keys())[0]
            # import pdb; pdb.set_trace()

    def build_statement(self, values):
        statement = {'qt_total_start':0,
                     'avg_price_start':0,
                     'values':[],
                     'qt_total_end':0,
                     'avg_price_end':0 }

        if len(values) == 1:
            operation = values[0]

            statement = {'qt_total_start':operation.qt_total_prev,
                         'avg_price_start':operation.avg_price_prev,
                         'ops':[operation],
                         'qt_total_end':operation.qt_total,
                         'avg_price_end':operation.avg_price }
        elif len(values) > 1:
            operation_start = values[0]
            operation_end = values[-1]
            statement = {'qt_total_start':operation_start.qt_total_prev,
                         'avg_price_start':operation_start.avg_price_prev,
                         'ops':values,
                         'qt_total_end':operation_end.qt_total,
                         'avg_price_end':operation_end.avg_price }
        return statement


    def months_build_data(self):
        months = {}
        months_operations = {}
        months_keys = self.months.keys()
        months_keys.reverse()
        for month in months_keys:
            month_data = self.months.get_month(month)
            months[month] = month_data
            months_operations[month] = dict(month_data['operations'])
        return (months, months_operations)


    def report(self):
        """ to refactor - was used for command line tests
        use the months_build_data method as web app """
        months_keys = self.months.keys()
        for month in months_keys:
            month_data = self.months.get_month(month)
            print("\n\n===================================== \n\n\n")
            print('Mês: {0} / Vendas no mes: {1}'.format(month, month_data['month_sell']))
            print('Lucro: {0} / PositionViewPrejuízo: {1} / Prejuizo acumulado: {2}'.format(month_data['month_gain'], month_data['month_loss'], month_data['cumulate_loss']))

            if month_data['tax']:
                print('Balanço mês: {1} / Imposto devido: {0}'.format(month_data['tax']['tax_amount'], month_data['tax']['final_balance']))

            for stock, values in month_data['operations'].items():
                # if stock != 'KLBN11':
                #     continue
                print
                print("Stock: %s" % (stock))
                for ops in values:
                    if ops['buy_sell'] == 'V':
                        if ops['profit']:
                            print("%s: %s " % ('Balance', ops['profit']))
                        if ops['loss']:
                            print("%s: -%s " % ('Balance', ops['loss']))
                statement = self.build_statement(values)
                print(statement)



    def current_position(self):
        """ to refactor - was used for command line tests
        use the months_build_data method as web app """

        """
        On the last day of the month you can sell your stocks where you are
        losing, to reduce from your futures gains.
        """
        position = []
        summary = defaultdict(Decimal)
        def get_stock_position(stock, values):
            try:
                current_price = self.current_prices[stock]
                buy_position = values.qt_total * values.avg_price

                if current_price['price']=='None':
                    raise StockNotFound

                curr_position = values.qt_total * round(Decimal(current_price['price']), 2)


                balance = curr_position - buy_position
                balance_pct = round((balance * 100 / buy_position), 2)

                if values.qt_total < 0:
                #     balance *= -1
                    balance_pct *= -1
                #
                # if stock == 'BRFS3':
                #     import pdb; pdb.set_trace()

                return (stock, values, Decimal(buy_position), Decimal(curr_position), Decimal(balance), balance_pct)
            except KeyError as e:
                # If KeyError 'avg_price', means that no buy input was provided.
                print("KeyError: %s" % str(e))
                # import pdb; pdb.set_trace()
                raise StockNotFound

        print("\n\n\nCurrent prices: %s" % (self.curr_prices_dt))
        for stock, values in self.stocks_wallet.items():
            if values.qt_total:
                try:
                    (stock, values, buy_position, curr_position, balance, balance_pct) = get_stock_position(stock, values)
                    # print("%s: Qt:%d - Buy avg: R$%.2f - Cur Price: R$%s - Buy Total: R$%.2f - Cur Total: R$%.2f - Balance: R$%.2f ( %.2f%s )" % (stock, values.qt_total'], values.avg_price'], self.current_prices[stock]['price'], buy_position, curr_position, balance, balance_pct, '%'))
                    position.append({
                        'stock': stock,
                        'qt': values.qt_total,
                        'buy_avg': values.avg_price,
                        'curr_price': self.current_prices[stock]['price'],
                        'buy_total':buy_position,
                        'cur_total':curr_position,
                        'balance': balance,
                        'balance_pct': balance_pct
                    })
                    summary['balance'] += balance
                    # import pdb; pdb.set_trace()
                    summary['buy_total'] += buy_position
                    summary['cur_total'] += curr_position


                except StockNotFound:
                    values.exception = StockNotFound('%s: StockNotFound (%s)'  % (values.stock, values.dt))
                    self.illegal_operation[values.stock].append(values)
        # import pdb; pdb.set_trace()
        if not summary['buy_total'] == 0:
            summary['balance_pct'] =  (100 * (summary['cur_total'] - summary['buy_total'])) / summary['buy_total']
        return (position, summary)


    def illegal_operations(self, illegal_operations):
        print("\n\n\n")
        print("Illigal operations")
        print("==================")
        for list_io in illegal_operations:
            for stock, values in list_io.items():
                for err in values:
                    print(err['exception'])


# Call from command line not working anymore.
# Lots of API changes.
if __name__ == "__main__":
    import argparse
    illegal_operations = []
    def get_args():
        """
        To get stock prices from your CSV file, call this script wiht arguments.
        python stock_price.py --path --file
        """
        parser = argparse.ArgumentParser()
        parser.add_argument('--mkt_type', default='VIS')
        parser.add_argument('--path', default='test_sample')
        parser.add_argument('--file', default='sample.csv')
        args = parser.parse_args()
        return args

    def handle_data(args):
        b3_tax_obj = ObjectifyData(mkt_type='VIS', path=args.path, file=args.file)
        return b3_tax_obj

    def gather_illegal_operation(illegal_operation):
        illegal_operations.append(illegal_operation)

    def months_reconcile(b3_tax_obj):
        months = b3_tax_obj.file2object()
        months.month_add_detail()
        return months

    def generate_reports(stocks_wallet, months):
        print("\n\nMercado à vista")
        print("===============")
        # report = Report()
        report = Report('/var/tmp/stock_price.json', stocks_wallet, months)

        report.report()

        report.get_current_quotations()
        report.current_position()
        gather_illegal_operation(report.illegal_operation)
        report.illegal_operations(illegal_operations)

    args = get_args()
    b3_tax_obj = handle_data(args)
    gather_illegal_operation(b3_tax_obj.illegal_operation)
    months = months_reconcile(b3_tax_obj)
    generate_reports(b3_tax_obj.stocks_wallet, months)







    exit(0)

    print("\n\nOpcoes PUT")
    print("==========")
    b3_tax_obj = ObjectifyData('OPV', path=args.path, file=args.file)
    months = b3_tax_obj.file2object()
    months.month_add_detail()
    report.report(months)
