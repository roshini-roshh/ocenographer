import os
import datetime
import copernicusmarine

def update_marine_datasets():
    # 1. Calculate dynamic date range (target 2-4 days behind real-time)
    today = datetime.date.today()
    start_date = (today - datetime.timedelta(days=16)).strftime("%Y-%m-%d")
    end_date = (today - datetime.timedelta(days=2)).strftime("%Y-%m-%d")

    sst_file = "daily_sst.nc"
    chl_file = "daily_chlorophyll.nc"

    print(f"[{datetime.datetime.now()}] Refreshing Marine Datasets ({start_date} to {end_date})...")

    # Clean up old files to ensure fresh write
    for file_path in [sst_file, chl_file]:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Notice: Could not remove {file_path}: {e}")

    # 2. Fetch Sea Surface Temperature (SST)
    try:
        print("Fetching latest SST dataset...")
        copernicusmarine.subset(
            dataset_id="METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2",
            variables=["analysed_sst"],
            minimum_longitude=65.0,
            maximum_longitude=90.0,
            minimum_latitude=5.0,
            maximum_latitude=25.0,
            start_datetime=f"{start_date}T00:00:00",
            end_datetime=f"{end_date}T23:59:59",
            output_filename=sst_file
        )
        print("[SUCCESS] SST data updated.")
    except Exception as e:
        print(f"[ERROR] SST update failed: {e}")

    # 3. Fetch Chlorophyll-a (CHL)
    try:
        print("Fetching latest Chlorophyll-a dataset...")
        copernicusmarine.subset(
            dataset_id="cmems_obs-oc_glo_bgc-plankton_nrt_l3-olci-4km_P1D",
            variables=["CHL"],
            minimum_longitude=65.0,
            maximum_longitude=90.0,
            minimum_latitude=5.0,
            maximum_latitude=25.0,
            start_datetime=f"{start_date}T00:00:00",
            end_datetime=f"{end_date}T23:59:59",
            output_filename=chl_file
        )
        print("[SUCCESS] Chlorophyll data updated.")
    except Exception as e:
        print(f"[ERROR] Chlorophyll update failed: {e}")

if __name__ == "__main__":
    update_marine_datasets()