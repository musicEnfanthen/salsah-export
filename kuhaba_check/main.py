# panda library
import pandas as pd
# system library
import sys

input_excel_file = "KH Bestand Total_mit Jahr.xlsx"
input_tab = "total bis 2006"
starting_row = 0

full_data = pd.read_excel(input_excel_file, sheet_name=input_tab)

print("start")

# range of rows (first part)
df_1 = full_data.iloc[starting_row:10]
# print number of rows
print("Total rows first Part: {0}".format(len(df_1)))

