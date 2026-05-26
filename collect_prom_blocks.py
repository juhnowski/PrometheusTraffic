import os
import shutil
import time
import urllib.request
import json
import random
from prometheus_client import CollectorRegistry, Gauge, Counter, push_to_gateway

OUTPUT_DIR = "./prom_bench_blocks"
PROM_DATA_DIR = "./prom_data/data"

def generate_and_push_metrics():
    registry = CollectorRegistry()

    # Сценарий 1: Высокий уровень дубликатов (константные статусы систем)
    g_dup = Gauge('system_status_code', 'Fixed status codes for testing', ['host', 'service'], registry=registry)
    
    # Сценарий 2: Денормализованная структура (динамические лейблы IoT датчиков)
    g_iot = Gauge('factory_sensor_reading', 'IoT sensor values', ['floor', 'device_id', 'firmware'], registry=registry)
    
    # Сценарий 3: Случайный бинарный шум (высокая энтропия float64 значений)
    c_noise = Counter('entropy_random_total', 'Random entropy source', ['source'], registry=registry)

    print("    [1/2] Генерация и отправка пакетов метрик в Pushgateway...")
    
    # Имитируем отправку данных порциями
    for step in range(10):
        # 1. Заполняем дубликаты
        for i in range(1000):
            status = 200 if i % 2 == 0 else 500
            g_dup.labels(host=f"srv-{i % 5}", service="nginx").set(status)

        # 2. Заполняем денормализованные лейблы
        for i in range(1000):
            val = 22.5 + (i % 5) * 0.5
            g_iot.labels(floor="alpha-floor", device_id=f"sensor-{i}", firmware="v1.0.3").set(val)

        # 3. Заполняем бинарный шум
        for i in range(1500):
            c_noise.labels(source="random_noise").inc(random.random() * 100)

        # Пушим текущий срез метрик в локальный Gateway
        push_to_gateway('127.0.0.1:9091', job='bench_job', registry=registry)
        time.sleep(0.5)

def trigger_prometheus_snapshot():
    """Вызывает Admin API Prometheus для немедленного создания snapshot-блока на диске."""
    print("    [2/2] Запрос к Prometheus Admin API на создание Snapshot...")
    
    # Строго IPv4 и корректный эндпоинт
    url = "http://127.0.0.1:9090/api/v1/admin/tsdb/snapshot"
    
    # Создаем пустой POST-запрос с необходимыми заголовками
    req = urllib.request.Request(
        url, 
        data=b"", # Пустой body, чтобы urllib сделал именно POST
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            return res["data"]["name"]
    except Exception as e:
        print(f"    [!] Ошибка вызова API: {e}. Убедитесь, что Prometheus запущен.")
        return None



def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Генерируем трафик метрик
    generate_and_push_metrics()
    
    # Даем Prometheus время (пару секунд), чтобы гарантированно проскрейпить Pushgateway несколько раз
    print("    Ожидание сбора метрик движком Prometheus...")
    time.sleep(5)
    
    snapshot_name = trigger_prometheus_snapshot()
    if not snapshot_name:
        return

    # Путь, куда Prometheus сохраняет свои снапшоты
    snapshot_dir = os.path.join(PROM_DATA_DIR, "snapshots", snapshot_name)
    
    # Внутри папки снапшота лежит один или несколько двухчасовых блоков (папки-хэши)
    blocks = [d for d in os.listdir(snapshot_dir) if os.path.isdir(os.path.join(snapshot_dir, d))]
    
    if not blocks:
        print("    [!] Ошибка: Блоки TSDB в снапшоте не найдены.")
        return

    print("\n[+] Сбор сырых файлов TSDB Prometheus для алгоритма...")
    file_counter = 0
    
    for block_uuid in blocks:
        block_path = os.path.join(snapshot_dir, block_uuid)
        
        # 1. Забираем файл индексов (метаданные серий и лейблы)
        index_src = os.path.join(block_path, "index")
        if os.path.exists(index_src):
            index_dest = os.path.join(OUTPUT_DIR, f"prometheus_block_{file_counter}_index.raw")
            shutil.copy(index_src, index_dest)
            print(f"    Сохранено: {index_dest} ({os.path.getsize(index_dest) // 1024} KB)")

        # 2. Забираем бинарные чанки с Gorilla-сжатием
        chunks_dir = os.path.join(block_path, "chunks")
        if os.path.exists(chunks_dir):
            for chunk_file in os.listdir(chunks_dir):
                chunk_src = os.path.join(chunks_dir, chunk_file)
                chunk_dest = os.path.join(OUTPUT_DIR, f"prometheus_block_{file_counter}_chunk_{chunk_file}.raw")
                shutil.copy(chunk_src, chunk_dest)
                print(f"    Сохранено: {chunk_dest} ({os.path.getsize(chunk_dest) // 1024} KB)")
                
        file_counter += 1

    print("\n[+] Сбор блоков для Prometheus успешно завершен!")

if __name__ == "__main__":
    main()
