import csv
from collections import defaultdict
from conf.conf import CEI_INPUT_PATH, CEI_OUTPUT_PATH

file_path = CEI_INPUT_PATH
data_dict = defaultdict(list)
fh = open(file_path)

while True:
    line = fh.readline()
    if not line:
        break

    if line.startswith('#'):
        continue

    data = line.split()

    if not data:
        continue

    # Daytrade - Still not working
    if data[7] == "ZERADA":
        continue

    if data[4] != '0,000':
        cp_vd = data[4]

    elif data[5] != '0,000':
        cp_vd = data[5]
    else:
        continue

    date_sort = data[1].split('/')
    date_sort = "%s%s%s" % (date_sort[2],date_sort[1],date_sort[0])
    date_sort = int(date_sort)

    cp_vd = cp_vd.replace(',', '.')
    data[6] = data[6].replace('.', '')
    total = float(cp_vd) * int(data[6])

    data_dict[date_sort].append([data[1], '', data[7][0], 'VIS', data[0], '', data[6], cp_vd, total, '', ''])

fh.close()





with open(CEI_OUTPUT_PATH, 'wb') as f:
    writer = csv.writer(f)
#    writer.writerows(csv_data)
    for key, value in sorted(data_dict.items(), reverse = True):
        for list in value:
            writer.writerow(list)

    # ', '.join(mylist)
