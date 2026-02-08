import csv
import os

class SolarExporter:
    @staticmethod
    def export_to_csv(filename, results):
        """
        Gera um arquivo CSV otimizado para Excel (padrão brasileiro)
        dentro da pasta 'data' do projeto.
        """
        if not results:
            print("[AVISO] Nenhum dado para exportar.")
            return
        
        # 1. Define o caminho da pasta 'data' (um nível acima de utils/)
        # Isso garante que a pasta seja criada na raiz do projeto
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_folder = os.path.join(base_dir, "data")

        # 2. Cria a pasta 'data' se ela não existir
        if not os.path.exists(data_folder):
            os.makedirs(data_folder)

        # 3. Garante a extensão .csv e define o caminho completo
        if not filename.endswith('.csv'):
            filename += '.csv'
        
        full_path = os.path.join(data_folder, filename)

        try:
            keys = results[0].keys()
            with open(full_path, 'w', newline='', encoding='utf-8-sig') as output_file:
                # Delimiter ';' para Excel BR
                dict_writer = csv.DictWriter(output_file, fieldnames=keys, delimiter=';')
                
                dict_writer.writeheader()
                
                for row in results:
                    # Converte ponto em vírgula para compatibilidade com Excel BR
                    formatted_row = {
                        k: str(v).replace('.', ',') if isinstance(v, (float, int)) else v 
                        for k, v in row.items()
                    }
                    dict_writer.writerow(formatted_row)
                    
            print(f"\n[SUCESSO] Dados exportados para: {full_path}")
            
        except PermissionError:
            print(f"\n[ERRO] O arquivo '{filename}' está aberto no Excel. Feche-o e tente novamente.")
        except Exception as e:
            print(f"\n[ERRO] Falha ao exportar: {e}")