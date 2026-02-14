import pandas as pd
import os

def consolidate_inpe_data():
    base_path = "data/inpe_labren/"
    output_path = os.path.join(base_path, "atlas_brasil_consolidado.parquet")
    
    print("🚀 Iniciando consolidação dos dados do INPE/LABREN...")

    # 1. Carregar Global (Base principal com 72.272 registros) 
    # O delimitador é ';' e o decimal é '.' [cite: 68, 69]
    df_global = pd.read_csv(os.path.join(base_path, "global_horizontal_means.csv"), sep=';')
    
    # 2. Carregar Difusa 
    df_diffuse = pd.read_csv(os.path.join(base_path, "diffuse_means.csv"), sep=';')

    # 3. Mesclar os dados baseando-se em LON e LAT [cite: 39]
    # Vamos renomear as colunas para diferenciar Global de Difusa
    months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    
    df_final = df_global[['LON', 'LAT'] + months].copy()
    
    for month in months:
        # Criamos colunas como 'JAN_glo' e 'JAN_dif'
        df_final[f"{month}_glo"] = df_global[month]
        df_final[f"{month}_dif"] = df_diffuse[month]
        # Removemos a coluna original do mês para não confundir
        if month in df_final.columns:
            df_final.drop(columns=[month], inplace=True)

    # 4. Salvar em Parquet (Requer 'pyarrow' ou 'fastparquet' instalado)
    df_final.to_parquet(output_path, index=False)
    print(f"✅ Sucesso! Arquivo consolidado gerado em: {output_path}")

if __name__ == "__main__":
    consolidate_inpe_data()