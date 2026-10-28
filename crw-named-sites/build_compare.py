"""Build the separate comparison test viewer from existing local data. No downloads."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
if __name__ == '__main__':
    template = (ROOT / 'compare_template.html').read_text(encoding='utf-8')
    for placeholder, name in [('__BUNDLE_JSON__', 'data/viewer_data.json'), ('__ONMS_JSON__', 'onms_boundaries.json')]:
        if template.count(placeholder) != 1:
            raise ValueError('Missing or duplicated placeholder: ' + placeholder)
        data = json.loads((ROOT / name).read_text(encoding='utf-8'))
        template = template.replace(placeholder, json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/'))
    target = ROOT / 'compare.html'
    tmp = target.with_suffix('.html.tmp')
    tmp.write_text(template, encoding='utf-8')
    tmp.replace(target)
    print('Open ' + str(target))
