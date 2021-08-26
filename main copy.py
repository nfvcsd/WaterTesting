#!/usr/bin/env python3
import xmltodict
from collections import defaultdict
from datetime import datetime
# import typing # comes by default now
from openpyxl import load_workbook

from openpyxl.workbook.workbook import Workbook
from openpyxl.chart import (
    LineChart,
    Reference
)
from openpyxl.chart.axis import DateAxis

wb_path = input("File: ").strip("'")
outputfile = input("Output File Name (With .xml extension): ")
def Average(list: list) -> float:
    return sum(list) / len(list)
with open(wb_path) as fd:
    doc = xmltodict.parse(fd.read())
#print(doc['Datalog']['Entry'])
i = 0
Data = {}
Date = ''
for entry in doc['Datalog']['Entry']:
    if i >= 2:
        try:
            Date = datetime.strptime(entry['Time'], '%m/%d/%Y %I:%M:%S %p')
        except ValueError:
            try:
                Date = datetime.strptime(entry['Time'], '%m/%d/%Y %H:%M:%S')
            except:
                Date = datetime.strptime(entry['Time'], '%Y/%m/%d %H:%M:%S')
        Day = Date.strftime('%m-%d-%Y')
        if Day not in Data:
            Data[Day] = {'CL2': [], "Flow": []}
        if len(entry['CH1']) > 1:
            Data[Day]['CL2'].append(float(entry['CH1'][0]['Data']))
        else:
            Data[Day]['CL2'].append(float(entry['CH1']['Data']))
        if len(entry['CH2']) > 1:
            Data[Day]['Flow'].append(float(entry['CH2'][0]['Data']))
        else:
            Data[Day]['Flow'].append(float(entry['CH2']['Data']))
    i+=1

for entry, value in Data.items():
    # print(entry, value)
    # print(value['CL2'])
    value['CL2'] = Average(value['CL2'])
    value['Flow'] = Average(value['Flow'])
# print(Data)

# Create New Excel Doc Here
nb = Workbook()
dest_filename = outputfile
ws1 = nb.active
ws1.title = "Averages"
i = 3
ws1['A1'] = "Date"
ws1['B1'] = "CL2"
ws1['C1'] = "Flow"
for key, value in Data.items():
    a_col = f'A{i}'
    b_col = f'B{i}'
    c_col = f'C{i}'
    ws1[a_col] = key
    ws1[b_col] = value['CL2']
    ws1[c_col] = value['Flow']
    i+=1
    print(key,value['CL2'],value['Flow'] )
chartData = Reference(ws1, min_col=2, min_row=1, max_col=4, max_row=30)
c1 = LineChart()
c1.title = "Daily Average"
c1.style = 12
c1.y_axis.title = "Value"
c1.y_axis.crossAx = 500
c1.x_axis = DateAxis(crossAx=100)
c1.x_axis.number_format = 'd-mm-yyyy'
c1.x_axis.majorTimeUnit = "days"
c1.x_axis.title = "Date"

c1.add_data(chartData, titles_from_data=True)
dates = Reference(ws1, min_col=1, min_row=2, max_row=30)
c1.set_categories(dates)
ws1.add_chart(c1, "E4")
nb.save(filename=dest_filename)