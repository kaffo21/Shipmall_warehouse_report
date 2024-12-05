import streamlit as st
import pandas
import os

from streamlit import set_page_config
from datetime import datetime
from streamlit.source_util import page_icon_and_name

# Timestamp of when the file was created - it is considered the date of the last update
# Path to the CSV file
file_path = "data/warehouse_report.csv"
# Get the creation time of the file
if os.path.exists(file_path):
    creation_time = os.path.getctime(file_path)
    # Convert it to a readable format
    creation_date = datetime.fromtimestamp(creation_time).strftime("%d-%m-%Y %H:%M")
else:
    creation_date = "File does not exist!"

# Nastavení globálního formátování pro zobrazení desetinných čísel
pandas.options.display.float_format = '{:.1f}'.format

# Data frame from file from Shoptet - product code, name and purchase price
df_products = pandas.read_csv("data/shoptet_products.csv", sep=";")
df_products["purchasePrice"] = pandas.to_numeric(
    df_products["purchasePrice"].str.replace(",", "."), # Replace commas with dots for decimals
    errors="coerce" # Invalid parsing will result in NaN
)

# Adding CZK currency to Purchase Price (it has to be string)
# Therefore we store purchase_price as int too in order to work with it later
# Plus calculating it without VAT (21%)
df_products["purchasePrice"] = df_products["purchasePrice"] / 1.21
df_products["purchasePrice"] = df_products["purchasePrice"].astype(float).round(1)
df_products["purchasePrice_int"] = df_products["purchasePrice"]
df_products["purchasePrice"] = df_products["purchasePrice"].astype(str) + " CZK"

# Handle missing values (optional) - missing values = 0
df_products["purchasePrice"] = df_products["purchasePrice"].fillna(0)


# Data frame from file warehouse_movement
df_wm = pandas.read_csv("data/warehouse_movements.csv", sep=";")
df_wm["Množ."] = pandas.to_numeric(
    df_wm["Množ."].str.replace(",", "."),  # Replace commas with dots for decimals
    errors="coerce"  # Invalid parsing will result in NaN
)

# Handle missing values (optional) - missing values = 0
df_wm["Množ."] = df_wm["Množ."].fillna(0).astype(int)

#Data frame contains only ID and Mnoz. - this is what we need
df_wm_sum = df_wm.groupby("ID", as_index=False)["Množ."].sum()


# Data frame from Warehouse report
df_wr = pandas.read_csv("data/warehouse_report.csv", sep=";")
df_wr["Volné"] = pandas.to_numeric(
    df_wr["Volné"].str.replace(",", "."), # Replace commas with dots for decimals
    errors="coerce"  # Invalid parsing will result in NaN
)

# Handle missing values (optional) - missing values = 0
df_wr["Volné"] = df_wr["Volné"].fillna(0).astype(int)


# DATA MERGING
# Merging of Warehouse_report and Warehous_movements
# Merging is "left" so it takes all rows from DataWarehouse
merged_data = pandas.merge(df_wr, df_wm_sum, on="ID", how="left")

# Merging with Shoptet Products report
# Merging is "left" so it takes all rows from Shoptet - what is not in Shoptet, is not merged
merged_data = pandas.merge(df_products, merged_data, left_on="code", right_on="ID", how="left")


# Add new column - average sales pers months
# Number od days between today and 1.9.2023
today = datetime.today()
starting_date = datetime(2023, 9, 1)
days =  (today - starting_date).days

merged_data["Prodeje/mesic (prumer)"] = merged_data["Množ."] / days * 30 # use of original columns name, before changing it
merged_data["Prodeje/mesic (prumer)"] =abs(merged_data["Prodeje/mesic (prumer)"].fillna(0).astype(int))
# After the calculation is done, we change Mnoz. tu integer
merged_data["Množ."] = abs(merged_data["Množ."].fillna(0).astype(int))

# Add new column - Warehouse Value
merged_data["Hodnota skladu v CZK"] = merged_data["Volné"].astype(float) * merged_data["purchasePrice_int"].astype(float) # use of original columns name, before changing it
merged_data["Hodnota skladu v CZK"] = merged_data["Hodnota skladu v CZK"].astype(float).round(1)
warehouse_value = merged_data["Hodnota skladu v CZK"].sum() # Calculation of total value of Warehouse - all products
merged_data["Hodnota skladu v CZK"] = merged_data["Hodnota skladu v CZK"].apply(lambda x: f"{x:.1f}")


# Add new column - Warehouse stock in days
# It is necessary to check we do not divide by zero or negative number
merged_data["Kolik dni vydrzi sklad?"] = "n/a"
for index, row in merged_data.iterrows():
    if abs(row["Prodeje/mesic (prumer)"]) > 0:
        if row["Volné"] / abs(row["Prodeje/mesic (prumer)"]) >0:
            merged_data.at[index, "Kolik dni vydrzi sklad?"] = row["Volné"] / abs(row["Prodeje/mesic (prumer)"])
            merged_data.at[index, "Kolik dni vydrzi sklad?"] *= 30 # Prepocitame mesiace na dni
            merged_data.at[index, "Kolik dni vydrzi sklad?"] = round(merged_data.at[index, "Kolik dni vydrzi sklad?"])
        else:
            merged_data.at[index, "Kolik dni vydrzi sklad?"] = 0 # Priradi 0, sklad je 0, treba objednat
    else:
        merged_data.at[index, "Kolik dni vydrzi sklad?"] = 500 # Priradi 500, lebo predaje su skoro nulove, zasoba vydrzi dlho

# Change of the columns names and their orders
merged_data = merged_data.rename(columns={"id": "Kod produktu", "name": "Nazev produktu", "purchasePrice": "Nakupni cena bez DPH", "Volné": "Skladem ks", "Množ.": "Prodeje od 1.9.2023"})
new_col_order = ["code", "ID", "Nazev produktu", "Nakupni cena bez DPH", "Skladem ks", "Hodnota skladu v CZK", "Prodeje/mesic (prumer)", "Prodeje od 1.9.2023", "Posl.příjem", "Kolik dni vydrzi sklad?"]
merged_data = merged_data[new_col_order]
merged_data = merged_data.drop(columns="code")
# Sort data by Hodnota skladu
merged_data = merged_data.sort_values(by="Kolik dni vydrzi sklad?", ascending=True)


# Here starts the web page making
set_page_config(
    page_title="Chytra Zed - warehouse report",
    page_icon="👊",
    layout="wide"
)

st.header("Chytra zed - report skladu")

df_all = pandas.DataFrame(merged_data)

# Highlight the rows if stock is for less than 30 days
stockdays = 30 # can be changed anytime
def highlight(row):
    if row["Kolik dni vydrzi sklad?"] < stockdays:
        return ["background-color: lightcoral"] * len(row)
    else:
        return [""] * len(row)

styled_df_all = df_all.style.apply(highlight, axis=1)
st.dataframe(styled_df_all, use_container_width=False)

st.write(f"Aktualni hodnota skladu je: {+ warehouse_value:,.1f} CZK bez DPH.")
st.write(f"Posledni aktualizace dat probehla: {creation_date}.")

# Vlastní styl pro červené pozadí a bílé písmo
st.markdown(f"""
    <span style="background-color: lightcoral; color: white; padding: 10px; border-radius: 5px;">
       Cervenou barvou zvyraznujeme produkty, kde zasoba vydrzi menej nez dni: {stockdays}
    </span></br></br>
""", unsafe_allow_html=True)

st.info("""
**Vysvětlivky**:\n
**Nákupní cena bez DPH**: NC jednoho kusu produktu.\n
**Hodnota skladu v CZK**: počet ks * NC jednoho kus = hodnota v CZK bez DPH, která leží skladem.\n
**Prodeje/měsíc (průměr)**: průměrný počet ks, který se prodá za měsíc. Je to hodnota "Prodeje od 1.9.2023"
přepočítaná aritmeticky na měsíce.\n
**Prodeje od 1.9.2023**: celkový počet ks, který se prodal od 1.9.2023 do data aktualizace.\n
**Posl.příjem**: datum, kdy naposledy byl daný produkt naskladněný do Shipmallu.\n
**Kolik dni vydrží sklad?**: počet ks na skladě / prodeje za měsíc... přepočtené na dny. Na jak dlouho máme cca zásobu.
""")

