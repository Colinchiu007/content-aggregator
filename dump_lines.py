with open(r'C:\Users\邱领\.qclaw\workspace\content-aggregator\src\content_aggregator\clients\llm_client.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i in range(23, 33):
    print(f'{i}: {repr(lines[i])}')