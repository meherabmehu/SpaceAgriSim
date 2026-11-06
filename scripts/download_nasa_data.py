from nasa_pipeline import download

if __name__ == "__main__":
    print(f"Acquired/verified {len(download())} selected NASA files")
