{
  description = "Стенд для сбора сырых TSDB чанков и индексов Prometheus";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux"; # Измените на aarch64-linux / x86_64-darwin при необходимости
      pkgs = import nixpkgs { inherit system; };
      
      pythonEnv = pkgs.python3.withPackages (ps: [
        ps.prometheus-client # Библиотека для генерации метрик Prometheus
      ]);
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        buildInputs = [
          pkgs.prometheus
          pkgs.prometheus-pushgateway
          pythonEnv
        ];

        shellHook = ''
          export PROM_DIR="$PWD/prom_data"
          export PORT_PROM=9090
          export PORT_GW=9091
          
          mkdir -p "$PROM_DIR/data" "$PROM_DIR/logs"

          # Генерируем конфигурацию prometheus.yml
          if [ ! -f "$PROM_DIR/prometheus.yml" ]; then
            echo "[Nix] Создание локальной конфигурации Prometheus..."
            cat <<EOF > "$PROM_DIR/prometheus.yml"
global:
  scrape_interval: 1s # Максимально частый сбор данных для быстрого наполнения блоков

scrape_configs:
  - job_name: 'pushgateway'
    honor_labels: true
    static_configs:
      - targets: ['127.0.0.1:9091']
EOF
          fi

          echo "--------------------------------------------------------"
          echo " Доступные команды Prometheus-стенда:"
          echo "   start-prom - Запустить Prometheus и Pushgateway"
          echo "   stop-prom  - Остановить все компоненты"
          echo "   run-bench  - Сгенерировать метрики и собрать блоки чанков"
          echo "--------------------------------------------------------"

          # Запуск сервисов в фоновом режиме с флагом --web.enable-admin-api (нужен для снапшотов)
          alias start-prom="
            pushgateway > \$PROM_DIR/logs/pushgateway.log 2>&1 & echo \$! > \$PROM_DIR/pushgateway.pid
            prometheus --config.file=\$PROM_DIR/prometheus.yml --storage.tsdb.path=\$PROM_DIR/data --web.enable-admin-api --web.listen-address=127.0.0.1:\$PORT_PROM > \$PROM_DIR/logs/prometheus.log 2>&1 & echo \$! > \$PROM_DIR/prometheus.pid
            echo '[Nix] Сервисы запущены!'
          "
          
          alias stop-prom="
            kill \$(cat \$PROM_DIR/prometheus.pid) && rm \$PROM_DIR/prometheus.pid
            kill \$(cat \$PROM_DIR/pushgateway.pid) && rm \$PROM_DIR/pushgateway.pid
            echo '[Nix] Сервисы остановлены.'
          "
          
          alias run-bench="python collect_prom_blocks.py"
        '';
      };
    };
}
