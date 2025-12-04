"""
Análise de métricas de tráfego e preparação de dados para treino de modelos ML.

Uso:
    python Data/analyze_metrics.py

Este script carrega os ficheiros CSV gerados pelo MetricsManager e:
1. Mostra estatísticas resumidas
2. Cria visualizações básicas (se matplotlib estiver disponível)
3. Prepara datasets para treino de modelos de previsão

Ficheiros de entrada (na pasta Data/):
- system_snapshots_*.csv: Estado do sistema ao longo do tempo
- congestion_*.csv: Níveis de congestionamento por cruzamento
- waiting_times_*.csv: Tempos de espera nos semáforos
- disruptions_*.csv: Perturbações ocorridas
- traffic_flow_*.csv: Fluxo de veículos
- intersection_metrics_*.csv: Métricas detalhadas por cruzamento
"""

import os
import glob
import csv
from datetime import datetime
from collections import defaultdict

DATA_DIR = "Data"


def load_latest_session_files():
    """Load the most recent session data files."""
    files = {}
    
    # Find all session files
    patterns = [
        "system_snapshots_*.csv",
        "congestion_*.csv", 
        "waiting_times_*.csv",
        "disruptions_*.csv",
        "traffic_flow_*.csv",
        "intersection_metrics_*.csv",
        "session_summary_*.csv"
    ]
    
    for pattern in patterns:
        matches = glob.glob(os.path.join(DATA_DIR, pattern))
        if matches:
            # Get the most recent file
            latest = max(matches, key=os.path.getmtime)
            file_type = pattern.split("_")[0] if "_" in pattern else pattern.replace("*.csv", "")
            files[file_type] = latest
    
    return files


def load_csv_data(filepath):
    """Load a CSV file and return headers and rows."""
    if not os.path.exists(filepath):
        return [], []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader, [])
        rows = list(reader)
    
    return headers, rows


def analyze_system_snapshots(filepath):
    """Analyze system snapshot data."""
    headers, rows = load_csv_data(filepath)
    
    if not rows:
        print("Sem dados de snapshots do sistema.")
        return
    
    print("\n" + "="*60)
    print("ANÁLISE DE SNAPSHOTS DO SISTEMA")
    print("="*60)
    print(f"Total de snapshots: {len(rows)}")
    
    # Calculate averages
    total_cars = [int(r[4]) for r in rows if r[4].isdigit()]
    total_stopped = [int(r[6]) for r in rows if r[6].isdigit()]
    avg_speeds = [float(r[7]) for r in rows if r[7].replace('.','').isdigit()]
    traffic_densities = [float(r[9]) for r in rows if r[9].replace('.','').isdigit()]
    
    if total_cars:
        print(f"\nCarros ativos:")
        print(f"  - Mínimo: {min(total_cars)}")
        print(f"  - Máximo: {max(total_cars)}")
        print(f"  - Média: {sum(total_cars)/len(total_cars):.1f}")
    
    if total_stopped:
        print(f"\nCarros parados:")
        print(f"  - Mínimo: {min(total_stopped)}")
        print(f"  - Máximo: {max(total_stopped)}")
        print(f"  - Média: {sum(total_stopped)/len(total_stopped):.1f}")
    
    if avg_speeds:
        print(f"\nVelocidade média:")
        print(f"  - Mínima: {min(avg_speeds):.2f}")
        print(f"  - Máxima: {max(avg_speeds):.2f}")
        print(f"  - Média: {sum(avg_speeds)/len(avg_speeds):.2f}")
    
    if traffic_densities:
        print(f"\nDensidade de tráfego:")
        print(f"  - Mínima: {min(traffic_densities):.3f}")
        print(f"  - Máxima: {max(traffic_densities):.3f}")
        print(f"  - Média: {sum(traffic_densities)/len(traffic_densities):.3f}")


def analyze_congestion(filepath):
    """Analyze congestion data."""
    headers, rows = load_csv_data(filepath)
    
    if not rows:
        print("\nSem dados de congestionamento.")
        return
    
    print("\n" + "="*60)
    print("ANÁLISE DE CONGESTIONAMENTO")
    print("="*60)
    print(f"Total de registos: {len(rows)}")
    
    # Group by intersection
    by_intersection = defaultdict(list)
    for row in rows:
        if len(row) > 4:
            intersection_id = row[3]
            try:
                congestion = float(row[4])
                by_intersection[intersection_id].append(congestion)
            except:
                pass
    
    print("\nCongestionamento médio por cruzamento:")
    for intersection_id, values in sorted(by_intersection.items()):
        avg = sum(values) / len(values)
        max_val = max(values)
        print(f"  {intersection_id}: média={avg:.3f}, máx={max_val:.3f}")


def analyze_waiting_times(filepath):
    """Analyze waiting time data."""
    headers, rows = load_csv_data(filepath)
    
    if not rows:
        print("\nSem dados de tempos de espera.")
        return
    
    print("\n" + "="*60)
    print("ANÁLISE DE TEMPOS DE ESPERA")
    print("="*60)
    print(f"Total de registos: {len(rows)}")
    
    # Calculate statistics
    wait_times = []
    for row in rows:
        if len(row) > 5:
            try:
                wait_times.append(float(row[5]))
            except:
                pass
    
    if wait_times:
        print(f"\nTempos de espera (segundos):")
        print(f"  - Mínimo: {min(wait_times):.1f}")
        print(f"  - Máximo: {max(wait_times):.1f}")
        print(f"  - Média: {sum(wait_times)/len(wait_times):.1f}")
        
        # Distribution
        short = len([w for w in wait_times if w < 10])
        medium = len([w for w in wait_times if 10 <= w < 30])
        long = len([w for w in wait_times if w >= 30])
        
        print(f"\nDistribuição:")
        print(f"  - Curto (<10s): {short} ({100*short/len(wait_times):.1f}%)")
        print(f"  - Médio (10-30s): {medium} ({100*medium/len(wait_times):.1f}%)")
        print(f"  - Longo (>30s): {long} ({100*long/len(wait_times):.1f}%)")


def analyze_disruptions(filepath):
    """Analyze disruption data."""
    headers, rows = load_csv_data(filepath)
    
    if not rows:
        print("\nSem dados de perturbações.")
        return
    
    print("\n" + "="*60)
    print("ANÁLISE DE PERTURBAÇÕES")
    print("="*60)
    print(f"Total de perturbações: {len(rows)}")
    
    # Count by type
    by_type = defaultdict(int)
    for row in rows:
        if len(row) > 3:
            by_type[row[3]] += 1
    
    print("\nPerturbações por tipo:")
    for dtype, count in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {dtype}: {count}")


def prepare_ml_dataset(output_file="Data/ml_training_data.csv"):
    """Prepare a combined dataset for ML model training."""
    files = load_latest_session_files()
    
    print("\n" + "="*60)
    print("PREPARAÇÃO DE DATASET PARA ML")
    print("="*60)
    
    if 'system' not in files:
        print("Dados de sistema não encontrados.")
        return
    
    _, snapshots = load_csv_data(files['system'])
    
    if not snapshots:
        print("Sem dados suficientes para gerar dataset.")
        return
    
    # Create combined dataset
    # Features: hour, traffic_density, total_cars, total_stopped, avg_speed, active_disruptions
    # Target: congestion indicator (high stopped / total_cars ratio)
    
    ml_data = []
    for row in snapshots:
        if len(row) >= 12:
            try:
                hour = int(row[2])
                total_cars = int(row[4])
                total_stopped = int(row[6])
                avg_speed = float(row[7])
                traffic_density = float(row[9])
                active_disruptions = int(row[10])
                speed_modifier = float(row[12])
                
                # Calculate congestion indicator
                congestion_ratio = total_stopped / max(1, total_cars)
                is_congested = 1 if congestion_ratio > 0.3 else 0
                
                ml_data.append([
                    hour,
                    traffic_density,
                    total_cars,
                    total_stopped,
                    avg_speed,
                    active_disruptions,
                    speed_modifier,
                    congestion_ratio,
                    is_congested
                ])
            except:
                pass
    
    if ml_data:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'hour', 'traffic_density', 'total_cars', 'total_stopped',
                'avg_speed', 'active_disruptions', 'speed_modifier',
                'congestion_ratio', 'is_congested'
            ])
            writer.writerows(ml_data)
        
        print(f"Dataset ML criado: {output_file}")
        print(f"Total de amostras: {len(ml_data)}")
        print(f"\nColunas:")
        print("  - hour: Hora do dia (0-23)")
        print("  - traffic_density: Densidade de tráfego (0-1)")
        print("  - total_cars: Total de carros na simulação")
        print("  - total_stopped: Carros parados")
        print("  - avg_speed: Velocidade média")
        print("  - active_disruptions: Perturbações ativas")
        print("  - speed_modifier: Modificador de velocidade")
        print("  - congestion_ratio: Rácio de congestionamento")
        print("  - is_congested: Classificação binária (1=congestionado)")
    else:
        print("Não foi possível gerar dataset ML.")


def main():
    print("\n" + "="*60)
    print("ANÁLISE DE MÉTRICAS DE TRÁFEGO")
    print("="*60)
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    files = load_latest_session_files()
    
    if not files:
        print("\nNenhum ficheiro de dados encontrado na pasta Data/")
        print("Execute a simulação primeiro para gerar dados.")
        return
    
    print(f"\nFicheiros encontrados:")
    for file_type, path in files.items():
        print(f"  - {file_type}: {os.path.basename(path)}")
    
    # Analyze each data type
    if 'system' in files:
        analyze_system_snapshots(files['system'])
    
    if 'congestion' in files:
        analyze_congestion(files['congestion'])
    
    if 'waiting' in files:
        analyze_waiting_times(files['waiting'])
    
    if 'disruptions' in files:
        analyze_disruptions(files['disruptions'])
    
    # Prepare ML dataset
    prepare_ml_dataset()
    
    print("\n" + "="*60)
    print("Análise concluída!")
    print("="*60)


if __name__ == "__main__":
    main()

