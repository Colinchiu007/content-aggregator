with open(r'C:\Users\邱领\.qclaw\workspace\content-aggregator\src\content_aggregator\clients\llm_client.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
print(f'Total lines: {len(lines)}')
for i, line in enumerate(lines):
    if 'content is None' in line:
        print(f'--- Found at line {i} ---')
        for j in range(max(0, i-3), min(len(lines), i+20)):
            print(f'{j}: {lines[j].rstrip()[:120]}')
        print('---')
        break
