# B3IRCalc
Calculation of income tax for operations of purchase and sale of assets on the Brazilian stock exchange, B3.

For options, it calculates only buy and sell operations. It doesn't calculates income tax for options that were exercised.


## Warning
A system like this is very, very, very complex. So There is no level of warranty that there is no error. This is much more for personal use. 

It is used as the core module of this web app [https://b3ircalc.online/](https://github.com/robson-koji/django_b3_ir_calc), also for personal use.

It is to be a Python module for application. Still a standalone script.

## B3 CEI File
on 2021 B3 changed CEI file format, so now the system uses the SINACOR format.

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
* Month statement
* Short sale
* Create Exception to all avoid zero values for buy, sell, avg_price, qt, qt_total, etc
