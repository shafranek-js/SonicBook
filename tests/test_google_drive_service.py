import pytest

import google_drive_service


def test_extract_google_drive_folder_id_accepts_raw_id():
    folder_id = "163XWqfZGOCE1AJf5SC4o7bM89uDKDNDF"
    assert google_drive_service.extract_google_drive_folder_id(folder_id) == folder_id


def test_extract_google_drive_folder_id_accepts_shared_folder_link():
    link = "https://drive.google.com/drive/folders/163XWqfZGOCE1AJf5SC4o7bM89uDKDNDF?usp=sharing"
    assert google_drive_service.extract_google_drive_folder_id(link) == "163XWqfZGOCE1AJf5SC4o7bM89uDKDNDF"


def test_extract_google_drive_folder_id_rejects_non_drive_link():
    with pytest.raises(RuntimeError, match="Only Google Drive shared folder links are supported here."):
        google_drive_service.extract_google_drive_folder_id("https://example.com/folders/123")
