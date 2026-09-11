import datetime
import copernicusmarine

# Set a 5-day buffer to ensure valid dataset bounds
today = datetime.date.today()
start_date = (today - datetime.timedelta(days=5)).strftime("%Y-%m-%d")
end_date = (today - datetime.timedelta(days=2)).strftime("%Y-%m-%d")

print(f"Fetching SST data for date range: {start_date} to {end_date}...")

try:
    copernicusmarine.subset(
        dataset_id="METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2",
        variables=["analysed_sst"],
        minimum_longitude=65.0,
        maximum_longitude=90.0,
        minimum_latitude=5.0,
        maximum_latitude=25.0,
        start_datetime=f"{start_date}T00:00:00",
        end_datetime=f"{end_date}T23:59:59",
        output_filename="daily_sst.nc"
    )
    print("[SUCCESS] SST data saved to 'daily_sst.nc'")
except Exception as e:
    print(f"[ERROR] Failed to download SST data: {e}")

print("Process finished!")