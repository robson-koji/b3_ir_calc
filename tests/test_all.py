import sys, os
import unittest
from datetime import datetime

from b3_ir_calc.ir_calc import ObjectifyData, Months, StockCheckingAccount


class ObjectifyDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.od = ObjectifyData(file='sample.csv', file_path='files/test_sample/')
        cls.months = cls.od.file2object()
        cls.csv_line = ['10/07/2019','1-Bovespa','C','VIS','TATA11 UNT N2','','100','28,69','2869','D']

    def test_read_line(self):
        """ Line of CSV to dict """
        self.assertIsInstance(self.od.read_line(self.csv_line), dict)

    def test_dict_keys(self):
        """ Test response of line to dict has expected keys """
        expected_keys = ['qt', 'buy_sell', 'unit_price', 'year_month_id', 'value', 'dt', 'stock']
        self.assertListEqual(self.od.read_line(self.csv_line).keys(), expected_keys)

    def test_two_digits_month(self):
        """ Standalone utility function """
        self.assertEquals('01', self.od.two_digits_month(1))

    """ This two tests test half of the system """
    def test_file_to_object(self):
        """ Test conversion from file to Months object  """
        self.assertIsInstance(self.months, Months)

    def test_object_has_dict(self):
        """ Test Months object has a dict _months """
        self.assertIsInstance(self.months._months, dict)


class MonthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mm = Months()
        cls.line_dict = {'year_month_id':'201901', 'dt':datetime.now, 'stock':'ABCD12', 'value':1.11, 'buy_sell': 'C' }


    def test_get_month(self):
        month = self.line_dict['year_month_id']
        month_dict = self.mm[month]

        """ Tests to be continued from here..."""

        #import pdb; pdb.set_trace()

        # Set operation attributes
        #self.mm.month_populate(month, stock_updated_instance, **line)

    """
    def test_subtract_one_month(self):
        # Isso e a funcao subtract_one_month vao mudar apos o refactoring de monthsGroup
        from collections import OrderedDict
        self.b3_tax.mm = OrderedDict([('201907',{}), ('201908',{}), ('201908',{}), ('201910',{}),
            ('201911',{}), ('201912',{}), ('202001',{}), ('202002',{})])

        self.assertEquals('201912', self.b3_tax.subtract_one_month('202001'))

    def test_objectify_stock(self):
        from datetime import datetime
        dt = datetime.strptime('1/7/2019', '%d/%m/%Y')
        line_dict = {'qt': 100, 'buy_sell': 'C', 'unit_price': 28.69, 'year_month_id': 201907, 'value': 2869.0, 'dt': dt, 'stock': 'TAEE11'}
        response_dict = {'_avg_price': 0, 'loss': 0, 'name': 'TAEE11', 'buy_sell': 'C', 'profit': 0, 'unit_price': 28.69, 'year_month_id': 201907, 'value': 2869.0, 'avg_price': 28.69, 'qt_total': 100, 'dt': datetime(2019, 7, 1, 0, 0), 'qt': 100, 'stock': 'TAEE11'}
        self.assertDictEqual(response_dict, self.b3_tax.objectify_stock(line_dict))
    """

class StockCheckingAccountTest(unittest.TestCase):
    pass
