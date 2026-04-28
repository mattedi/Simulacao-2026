import pandas as pd
import numpy as np

file_names = ['data_01.csv', 'data_02.csv', 'data_03.csv']
possible_headers = ['situations', 'situation', 'Status', 'Sit.']

all_values = []

for file in file_names:
    try:
        df = pd.read_csv(file)
        
        target_col = next((col for col in possible_headers if col in df.columns), None)
        
        if target_col:
            all_values.extend(df[target_col].tolist())
            print(f"Successfully read '{target_col}' from {file}")
        else:
            print(f"Warning: No matching situation column found in {file}")
            
    except FileNotFoundError:
        print(f"Error: {file} not found.")

numpy_array = np.array(all_values)

print("\nFinal NumPy Array Shape:", numpy_array.shape)
print(numpy_array)