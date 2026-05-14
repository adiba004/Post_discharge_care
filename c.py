import gspread

# 1. Authenticate using your downloaded JSON file
gc = gspread.service_account(filename='pp.json')

# 2. Open the sheet by its name (as it appears in your Drive)
sh = gc.open("call logs")

# 3. Select the first worksheet
worksheet = sh.get_worksheet(0)

# 4. Read all data
data = worksheet.get_all_records()
print(data)

