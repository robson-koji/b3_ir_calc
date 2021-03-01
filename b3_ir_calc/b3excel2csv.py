# -*- coding: utf-8 -*-
from datetime import datetime
from os import devnull

import pandas as pd
import csv, xlrd

from django.conf import settings


def get_broker_client(empDfObj):
    cod_broker = False
    for index, row in empDfObj.iterrows():
        try:
            if row[7] == 'Participante de Negociação / Cliente':
                cod_broker = True
                continue
            elif cod_broker:
                return row[7].split(' - ')
        except:
            raise


def excel_to_csv(path, file):
    try:
        #file_path_excel = "/home/robson/Downloads/InfoCEI (17).xls"
        if path:
            path = path.replace('/media/', '')
            path = "%s%s" % (settings.MEDIA_ROOT, path)
        else:
            path = settings.MEDIA_ROOT

        file_path_excel = "%s/%s" % (path, file)
        file_path_csv = "%s/%s" % (path, file.replace('.xls', '.csv'))

        wb = xlrd.open_workbook(file_path_excel, logfile=open(devnull, 'w'))
        empDfObj = pd.read_excel(wb, engine='xlrd')

        try:
            (broker, client) = get_broker_client(empDfObj)
        except:
            raise

        df = pd.DataFrame()
        df = df.append({0:broker, 1:client}, ignore_index=True)
        df = df.append({}, ignore_index=True)

        df2 = pd.DataFrame()
        data_table = False
        for index, row in empDfObj.iterrows():
            # Identify table data header
            if row[3] == 'C/V' and row[4] == 'Mercado' and row[5] == 'Prazo' and row[8] == 'Quantidade':
                data_table = True
                continue

            # Identify end of table data
            if pd.isna(row[3]) and pd.isna(row[4]) and pd.isna(row[4]) and pd.isna(row[8]):
                continue

            # While table data
            if data_table:
                datetime_object = datetime.strptime(row[1].strip(), '%d/%m/%y')

                # Errando aqui. Acertar na view para passar correamente.
                mes = datetime_object.month
                if mes < 10:
                    mes = '0' + str(mes)
                dia = datetime_object.day
                if dia < 10:
                    dia = '0' + str(dia)

                row[1] = "%s/%s/%s" % (dia, mes, datetime_object.year)

                # import pdb; pdb.set_trace()
                if row[4].strip() == u'Mercado a Vista':
                    row[4] ='VIS'
                elif row[4].strip() == u'Opção de Venda':
                    row[4] ='OPV'
                elif row[4].strip() == u'Opção de Compra':
                    row[4] ='OPC'
                else:
                    row[4] ='NNN'

                # Estah errando aqui. Acertar a view para receber corretamente.
                row[9] = str(row[9]).replace('.', ',')
                row[10] = str(row[10]).replace('.', ',')
                # print(row)

                # import pdb; pdb.set_trace()

                df2 = df2.append({0:row[1], 1:'', 2:row[3].strip(), 3:row[4], 4:row[6], 5:'', 6:str(row[8]), 7:row[9], 8:row[10], 9:""}, ignore_index=True)

        # Reverse order
        df2 = df2[::-1]

        df = df.append(df2)
        # import pdb; pdb.set_trace()
        df.to_csv(file_path_csv, header=False, index=False, encoding='utf-8') #, quoting=csv.QUOTE_ALL)
    except Exception as e:
        raise
