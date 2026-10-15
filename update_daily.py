import json
from pathlib import Path
p=Path('data/sources.json')
sources=json.loads(p.read_text(encoding='utf-8')).get('sources',[])
print(f'Configured approved public sources: {len(sources)}')
print('Starter workflow executed successfully.')
