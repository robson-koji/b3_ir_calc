import unittest
from ir_calc import b3Tax




class b3TaxTest(unittest.TestCase):
    def setUp(self):
        self.b3_tax = b3Tax('abc')

    def test_two_digits_month(self):
        self.assertEquals('01', self.b3_tax.two_digits_month(1))

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
