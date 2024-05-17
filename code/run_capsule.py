""" Export NWB file with subject information """
import json
import re
import argparse
from pathlib import Path
import pytz
from datetime import datetime

from pynwb import NWBHDF5IO, NWBFile
from pynwb.file import Subject
from hdmf_zarr import NWBZarrIO
from uuid import uuid4

DOC_DB_HOST = "api.allenneuraldynamics.org"
DOC_DB_DATABASE = "metadata"
DOC_DB_COLLECTION = "data_assets"

data_folder = Path("../data")
results_folder = Path("../data")

# Create an argument parser
parser = argparse.ArgumentParser(description="Convert subject info to NWB")

# this allows to pass positional argument (in Code Ocean) or optional argument (from API/CLI)
backend_group = parser.add_mutually_exclusive_group()
backend_help = "NWB backend. It can be either 'hdf5' or 'zarr'."
backend_group.add_argument("--backend", choices=["hdf5", "zarr"], help=backend_help)
backend_group.add_argument("static_backend", nargs="?", default="hdf5", help=backend_help)


data_asset_group = parser.add_mutually_exclusive_group()
data_asset_help = (
    "Path to the data asset of the session. When provided, the metadata are fetched from the "
    "AIND metadata database. If None, and the attached data asset is used to fetch relevant "
    "metadata."
)
data_asset_group.add_argument("--asset_name", type=str, help=data_asset_help)
data_asset_group.add_argument("static_asset_name", nargs="?", help=data_asset_help)


def run():
    # Parse the command-line arguments
    args = parser.parse_args()
    backend = args.backend or args.static_backend
    asset_name = args.asset_name or args.static_backend

    print(f"Backend: {backend} -- Asset Name: {asset_name}")

    if backend == "hdf5":
        io_class = NWBHDF5IO
    elif backend == "zarr":
        io_class = NWBZarrIO
    else:
        raise ValueError(f"Unknown backend: {backend}")

    if asset_name is not None:
        from aind_data_access_api.document_db import MetadataDbClient

        doc_db_client = MetadataDbClient(
            host=DOC_DB_HOST,
            database=DOC_DB_DATABASE,
            collection=DOC_DB_COLLECTION,
        )
        if "ecephys" in asset_name:
            modality = "ecephys"
        elif "multiplane-ophys" in asset_name:
            modality = "multiplane-ophys"
        subject_match = re.search(r"_(\d+)_", asset_name)
        if subject_match:
            subject_id = subject_match.group(1)
        date_match = re.search(r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})", asset_name)
        if date_match:
            time = date_match.group(1)

        results = doc_db_client.retrieve_data_asset_records(
            filter_query={
                "$and": [{"_name": {"$regex": f"{modality}.*{time}"}}, {"subject.subject_id": f"{subject_id}"}]
            },
            paginate_batch_size=100,
        )
        if not results:
            print("No data records found.")
            raise Exception("No data records found.")

        data_description = results[0].data_description
        subject_metadata = results[0].subject
    else:
        # In this case we expect a single data asset folder as input
        data_assets = [p for p in data_folder.iterdir() if p.is_dir()]
        if len(data_assets) != 1:
            raise ValueError(f"Expected exactly one data asset attached, got {len(data_assets)}")
        data_asset = data_assets[0]
        data_description_file = data_asset / "data_description.json"
        subject_metadata_file = data_asset / "subject.json"
        assert data_description_file.is_file(), f"Missing data description file: {data_description_file}"
        assert subject_metadata_file.is_file(), f"Missing subject metadata file: {subject_metadata_file}"
        with open(data_description_file) as f:
            data_description = json.load(f)
        with open(subject_metadata_file) as f:
            subject_metadata = json.load(f)

    dob = subject_metadata["date_of_birth"]
    subject_dob_utc_datetime = datetime.strptime(dob, "%Y-%m-%d").replace(tzinfo=pytz.UTC)

    date_format = "%Y-%m-%dT%H:%M:%S.%f%z"
    session_start_date_string = data_description["creation_time"]
    session_id = data_description["name"]
    institution = data_description["institution"]["name"]

    # Use strptime to parse the string into a datetime object
    session_start_date_time = datetime.strptime(session_start_date_string, date_format)
    subject_age = session_start_date_time - subject_dob_utc_datetime

    age = "P" + str(subject_age) + "D"
    subject = Subject(
        subject_id=subject_metadata["subject_id"],
        species=subject_metadata["species"]["name"],
        sex=subject_metadata["sex"][0].upper(),
        date_of_birth=subject_dob_utc_datetime,
        age=age,
        genotype=subject_metadata["genotype"],
        description=None,
        strain=subject_metadata["background_strain"] or subject_metadata["breeding_group"],
    )

    # Store and write NWB file
    nwbfile = NWBFile(
        session_description="Test File",
        identifier=str(uuid4()),
        session_start_time=session_start_date_time,
        institution=institution,
        subject=subject,
        session_id=session_id,
    )

    # Naming Convention should be decided by AIND Schema.
    # It seems like the subject/processing/etc. Json
    # Files should also be added to the results folder?
    with io_class(results_folder / f"{asset_name}.nwb", mode="w") as io:
        io.write(nwbfile)


if __name__ == "__main__":
    run()
