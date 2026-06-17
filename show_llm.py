with open(r'C:\Users\邱领\.qclaw\workspace\content-aggregator\src\content_aggregator\clients\llm_client.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for j in range(215, 270):
    print(f'{j}: {lines[j].rstrip()[:130]}')
