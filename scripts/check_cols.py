import pandas as pd
df = pd.read_parquet('/root/ultimate_engine/training_data_hybrid.parquet')
print('Columns:', df.columns.tolist())
print('First row:', df.iloc[0].to_dict())
