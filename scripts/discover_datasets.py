from nasa_pipeline import discover

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Verify all 13 requested NASA studies")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    manifest = discover(refresh=args.refresh)
    print(f"Verified {len(manifest['datasets'])} NASA OSDR studies")
