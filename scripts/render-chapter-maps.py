"""Render the chapter concept maps in desktop and mobile compositions (stdlib only)."""
from pathlib import Path
from html import escape
import json

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'docs/diagrams'
ICONS = {
 'server':'M3 3h18v7H3z M3 14h18v7H3z M6 6h1 M6 17h1 M11 6h7 M11 17h7',
 'chip':'M6 6h12v12H6z M9 1v4 M15 1v4 M9 19v4 M15 19v4 M1 9h4 M1 15h4 M19 9h4 M19 15h4',
 'folder':'M2 6h8l2 3h10v12H2z M2 6V3h8l2 3h8v3',
 'key':'M14 5a5 5 0 1 1-4 8L3 20H1v-4l8-7 M4 15l3 3',
 'route':'M3 5h12 M12 2l3 3-3 3 M21 19H9 M12 16l-3 3 3 3 M3 5v10a4 4 0 0 0 4 4 M21 19V9a4 4 0 0 0-4-4',
 'trace':'M3 3h18v18H3z M6 8h12 M6 12h8 M6 16h10',
 'check':'M4 12l5 5L21 5 M21 12v8H3V3h12',
 'pause':'M8 4v16 M16 4v16',
}

def text(x,y,value,size=18,weight=400,fill='#203e56'):
 return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}">{escape(value)}</text>'

def render(item,mobile=False):
 kind=item['kind']; nodes=item['nodes']; width=360 if mobile else 720
 # Typography is composed at its final display scale, including a separate mobile layout.
 padding=20 if mobile else 28
 if kind=='lanes':
  positions=[(padding,76+i*(126 if mobile else 91),width-2*padding,112 if mobile else 77) for i in range(len(nodes))]
 elif mobile:
  positions=[(padding,76+i*133,width-2*padding,108) for i in range(len(nodes))]
 elif kind in ('grid','compare'):
  positions=[(padding+(i%2)*340,76+(i//2)*158,324,138) for i in range(len(nodes))]
 else:
  cardw=(width-2*padding-(len(nodes)-1)*24)/len(nodes)
  positions=[(padding+i*(cardw+24),76,cardw,160) for i in range(len(nodes))]
 end=max(y+h for _,y,_,h in positions); height=end+22
 result=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-labelledby="title desc">',f'<title id="title">{escape(item["title"])}</title><desc id="desc">{escape(item["description"]+" "+item["footer"])}</desc>',f'<rect width="{width}" height="{height}" rx="12" fill="#f4fafc"/>','<g font-family="-apple-system,BlinkMacSystemFont,PingFang SC,Microsoft YaHei,sans-serif">',text(padding,40,item['title'],19 if mobile else 23,600)]
 for i,(node,(x,y,w,h)) in enumerate(zip(nodes,positions)):
  result.append(f'<g id="step-{i+1}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#ffffff" stroke="#c8dfe9"/>')
  result.append(f'<g transform="translate({x+15},{y+15})" fill="none" stroke="#296583" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="{ICONS[node["icon"]]}"/></g>')
  if kind=='lanes':
   result.append(text(x+52,y+33,node['title'],18,600))
   if mobile:
    parts=node['body'].split(' → ')
    result.append(text(x+16,y+68,' → '.join(parts[:2]),16))
    result.append(text(x+16,y+92,'→ '+parts[2],16))
   else: result.append(text(x+125,y+33,node['body'],19))
  else:
   result.append(text(x+16 if not mobile and kind=='flow' else x+52,y+61 if not mobile and kind=='flow' else y+33,node['title'],17 if not mobile and len(nodes)==4 and kind=='flow' else 18,600))
   for j,line in enumerate(node['body'].split('\n')):
    result.append(text(x+16,y+(95 if not mobile and kind=='flow' else 67)+j*25,line,16 if mobile or (kind=='flow' and len(nodes)==4) else 17))
  result.append('</g>')
  if kind=='flow' and i<len(nodes)-1:
   if mobile:
    ax=x+w/2; ay=y+h+4
    result.append(f'<path d="M{ax} {ay}v17m-4-5 4 5 4-5" stroke="#477f9c" stroke-width="1.5" fill="none"/>')
   else:
    ax=x+w+3;ay=y+h/2
    result.append(f'<path d="M{ax} {ay}h18m-5-4 5 4-5 4" stroke="#477f9c" stroke-width="1.5" fill="none"/>')
 result.extend(['</g>','</svg>'])
 return '\n'.join(result)+'\n'

def main():
 for item in json.loads((DIRECTORY/'chapter-maps.json').read_text(encoding='utf-8'))['diagrams']:
  for mobile in (False,True):
   suffix='.mobile' if mobile else ''
   (DIRECTORY/(item['id']+suffix+'.svg')).write_text(render(item,mobile),encoding='utf-8')
 print('Rendered 12 concept maps × 2 reading widths')

if __name__=='__main__': main()
