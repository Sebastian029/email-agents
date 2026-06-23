import pandas as pd
from sklearn.model_selection import train_test_split

INPUT_FILE = "newsgroups_labeled.csv"
TRAIN_FILE = "train_data.csv"
TEST_FILE = "test_data.csv"

def split_csv():
    df = pd.read_csv(INPUT_FILE)
    print(f"Wczytano {len(df)} przykładów z {INPUT_FILE}")

    train_df, test_df = train_test_split(
        df,
        test_size=0.5,
        random_state=42,
        stratify=df["label"]
    )


    train_df.to_csv(TRAIN_FILE, index=False)
    test_df.to_csv(TEST_FILE, index=False)


if __name__ == "__main__":
    split_csv()