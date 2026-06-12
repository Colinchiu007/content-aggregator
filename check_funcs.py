with open(r'C:\Users\邱领\.qclaw\workspace\content-aggregator\src\content_aggregator\clients\llm_client.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
print(f'Total: {len(lines)} lines')
for i, line in enumerate(lines):
    if '_is_reasoning' in line or '_extract_final' in line:
        print(f'{i}: {line.rstrip()[:100]}')
