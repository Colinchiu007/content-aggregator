#!/usr/bin/env python3
with open(r'C:\Users\邱领\.qclaw\workspace\content-aggregator\src\content_aggregator\clients\llm_client.py', 'r', encoding='utf-8') as f:
    content = f.read()
idx = content.find('reasoning')
found = 0
while idx != -1 and found < 20:
    print(f'--- idx={idx} ---')
    print(content[max(0,idx-50):idx+200])
    print()
    idx = content.find('reasoning', idx+1)
    found += 1