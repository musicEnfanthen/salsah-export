# panda library
import pandas as pd
# mysql library
import pymysql
# my json handler
import json
# system library
import sys

photos = {}
not_found = []
input_excel_file = "KH Bestand Total_mit Jahr.xlsx"
input_tab = "total bis 2006"
starting_row = 0
ending_row = 1000
# ending_row = 17983


def save(file_name, data):
    try:
        with open(file_name, 'w') as outfile:
            json.dump(data, outfile)
    except Exception as err:
        print(err, file_name)
        raise SystemExit(0)


def mysql_request(row_number, photo_name):
    try:
        conn = pymysql.connect(host='localhost', port=3306, user='root', password='imago', database='salsah')

        cursor = conn.cursor(pymysql.cursors.DictCursor)

        sql = "SELECT * FROM `location` WHERE `origname` LIKE '%{name}%'".format(name=photo_name)

        cursor.execute(sql)

        results = cursor.fetchall()

        if len(results) == 0:
            print("empty", row_number, photo_name)
            not_found.append({"excel-row": row_number, "filename": photo_name})
        # for row_result in results:
        #     print(row_result)

        print("----- {0} ------".format(row_number))

        conn.close()
        cursor.close()

    except Exception as err:
        print(err)
        raise SystemExit(0)


full_data = pd.read_excel(input_excel_file, sheet_name=input_tab)

# range of rows (first part)
df = full_data.iloc[starting_row:ending_row]
# print number of rows
print("Total rows: {0}".format(len(df)))

# iterates through the rows
for index, row in df.iterrows():
    # makes sure there is no empty strings
    if row[0].strip():
        # passes the photo name
        mysql_request(index+2, row[0])


print("Total missing: {0}".format(len(not_found)))
photos["missing"] = not_found
save("output.json", photos)
