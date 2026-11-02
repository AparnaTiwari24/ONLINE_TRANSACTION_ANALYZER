import pandas as pd

# --- Input corrected CSVs ---
gpay_file = "transactions_corrected_gpay.csv"
paytm_file = "transactions_categorized_paytm.csv"

# --- Output combined file ---
output_file = "transactions_training.csv"

def merge_corrected_files(gpay_path, paytm_path, out_path):
    # Read both corrected files
    df_gpay = pd.read_csv(gpay_path)
    df_paytm = pd.read_csv(paytm_path)

    # Combine rows
    df_combined = pd.concat([df_gpay, df_paytm], ignore_index=True)

    # Drop duplicates if any
    df_combined.drop_duplicates(inplace=True)

    # Save final training file
    df_combined.to_csv(out_path, index=False)
    print(f"✔ Merged training file created: {out_path}")

if __name__ == "__main__":
    merge_corrected_files(gpay_file, paytm_file, output_file)
