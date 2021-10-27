# panda library
import pandas as pd
# mysql library
import pymysql
# my json handler
import json
# system library

all_res_id = []
all_ark = []
all_file_name = []
all_org_name = []


def save(file_name, data):
    try:
        with open(file_name, 'w') as outfile:
            json.dump(data, outfile)
    except Exception as err:
        print(err, file_name)
        raise SystemExit(0)


def get_resources():
    try:
        conn = pymysql.connect(host='localhost', port=3306, user='root', password='imago', database='salsah')

        cursor = conn.cursor(pymysql.cursors.DictCursor)

        sql = "SELECT `resource`.`handle_id`, `resource`.`id`, `location`.`filename`, `location`.`origname` " \
               "FROM `resource` INNER JOIN `location`" \
               "ON `resource`.`id` = `location`.`resource_id`" \
               "WHERE `resource`.`project_id` = 12"

        cursor.execute(sql)

        results = cursor.fetchall()

        conn.close()
        cursor.close()

        ids = {}
        new_result = []
        no_ark = 0
        for row_result in results:
            if row_result['id'] not in ids:
                new_result.append(row_result)
                ids[row_result['id']] = "0"

            # Checks if there is resource without an arc
            if not row_result['handle_id']:
                no_ark = no_ark + 1
                # print("Empty", row_result['id'], row_result['handle_id'], no_ark)

        print("Total of res with no ARK: ", no_ark)

        return new_result

    except Exception as err:
        print(err)
        raise SystemExit(0)


print("Start extracting")

all_resources = get_resources()

for resource in all_resources:
    all_res_id.append(resource['id'])
    all_ark.append(resource['handle_id'])
    all_file_name.append(resource['filename'])
    all_org_name.append(resource['origname'])

df_info = pd.DataFrame({
    'ID (mysql)': all_res_id,
    'ARK': all_ark,
    'File Name': all_file_name,
    'Original Name': all_org_name
})

# Create a Pandas Excel writer using XlsxWriter as the engine.
writer_info = pd.ExcelWriter("kuhaba_data_info.xlsx", engine='xlsxwriter')

df_info.to_excel(writer_info, sheet_name="Data")

writer_info.save()
