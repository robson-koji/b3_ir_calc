# b3_ir_calc
Calculte income tax for B3(BM&FBOVESPA) stocks and options operations. 

For options, it calculates only buy and sell operations. It doesn't calculates income tax for options that were exercised.


To be a Python module for application. Still a standalone script.

## Clone
git clone https://gitlab.com/robson.koji/b3_ir_calc.git

## Test
python setup.py test
There is a sample CSV file with dummy data included for tests.

## pip
Download with pip. **Still not usefull, because it is a standalone script** 

pip install git+https://gitlab.com/bv_fapesp/django_excel_csv#egg=django_excel_csv

## TODO
* Sort by date before processing
* Sort buy/sell - buy first for workflow consistency
* Asset name change (sometimes it change)
* Daytrade
* Subtract broker fees
* ~~Options~~ 
* Monthly statement
* Short sale
