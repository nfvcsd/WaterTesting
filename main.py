#!/usr/bin/env python3
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
outputfile = input("Output File Name (With .xlsx extension): ")
# print(wb_path)
wb = load_workbook(filename=wb_path)
# Don't actually need this. It automatically comes as a datetime object
def ConvertStringToDate(string: str) -> datetime:
    date_time_obj = datetime.strptime(string, '%y/%m/%d %H:%M:%S')
    return date_time_obj
def Average(list: list) -> float:
    return sum(list) / len(list)
sheet_ranges = wb['Sheet1']
offset = 0
date = ''
CL2data = defaultdict(list)
FlowData = defaultdict(list)
for x in sheet_ranges['A']:
    if offset >= 16:
        cl2 = f'B{offset}'
        flow = f"C{offset}"
        CL2data[str(x.value.date())].append(sheet_ranges[cl2].value)
        FlowData[str(x.value.date())].append(sheet_ranges[flow].value)

    offset +=1
# print(dict(CL2data))
# print(dict(FlowData))

Data = {}
for key, value in dict(CL2data).items():
    if key not in Data:
        Data[key] = {}
    dayCL2Average = Average(value)
    Data[key]["CL2"] = dayCL2Average
    # print(f"{key}: {dayCL2Average}")
for key, value in dict(FlowData).items():
    if key not in Data:
        Data[key] = {}
    dayFlowAverage = Average(value)
    Data[key]["Flow"] = dayFlowAverage
    # print(f"{key}: {dayFlowAverage}")
for key, value in Data.items():
    print(f"{key}: {value}")

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
c1.x_axis.number_format = 'd-mmm'
c1.x_axis.majorTimeUnit = "days"
c1.x_axis.title = "Date"

c1.add_data(chartData, titles_from_data=True)
dates = Reference(ws1, min_col=1, min_row=2, max_row=30)
c1.set_categories(dates)
ws1.add_chart(c1, "E4")
nb.save(filename=dest_filename)