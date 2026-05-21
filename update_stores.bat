@echo off
echo Updating store list...
python -c "import urllib.request, ssl, json; ctx = ssl.create_default_context(); req = urllib.request.Request('https://www.mcc.co.il/bs2/datasets/mcccard.json', headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.mcc.co.il/'}); data = json.loads(urllib.request.urlopen(req, context=ctx).read().decode('utf-8')); open('mcccard.json', 'w', encoding='utf-8').write(json.dumps(data, ensure_ascii=False)); print(f'Updated: {len(data)} stores')"
git add mcccard.json
git commit -m "Update store list"
git push
echo Done!
pause
