#!/usr/bin/env bash
nvidia-smi --query-gpu=name,power.limit,memory.used,utilization.gpu --format=csv
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
/mnt/c/Windows/System32/tasklist.exe 2>/dev/null | grep -i -E "r5apex|apex|steam|game" || echo "no game process"
pgrep -af "p3_count_timing|p4_forget_timing|e3_train" || echo "no trainer running"
